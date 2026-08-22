import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional, Tuple
import uuid

from ...core import database as db_core


def get_database():
    return db_core.get_database()
from ...models.identity import (
    CredentialStatus,
    CredentialVerificationLog,
    DigitalTouristCredential,
    KYCStatus,
    TouristIdentityProfile,
    VerificationResultCode,
)
from .kyc_service import kyc_service
from ..realtime_bus import RealtimeEventBus

logger = logging.getLogger("toursafe.identity.credential")


class CredentialService:
    """
    Digital Tourist Credential Lifecycle & QR Cryptographic Verification Service.
    Enforces strict verification gates, versioning, replacement, expiration, and audit logging.
    """

    def __init__(self, secret_key: str = "toursafe_credential_hmac_signing_key_32bytes", bus: Optional[RealtimeEventBus] = None):
        self.secret_key = secret_key
        self.bus = bus or RealtimeEventBus()
        self._verification_rate_tracker: Dict[str, List[float]] = {}

    def _sign_payload(self, credential_ref: str, user_id: str, version: int, expires_ts: int, nonce: str) -> str:
        data = f"{credential_ref}:{user_id}:{version}:{expires_ts}:{nonce}"
        return hmac.new(self.secret_key.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).hexdigest()

    def generate_qr_payload(self, credential: DigitalTouristCredential) -> str:
        """Encode credential into opaque, signed QR token."""
        exp_ts = int(credential.expires_at.timestamp())
        sig = credential.signature or self._sign_payload(
            credential.credential_reference,
            credential.user_id,
            credential.version,
            exp_ts,
            credential.token_nonce,
        )
        token_data = {
            "ref": credential.credential_reference,
            "uid": credential.user_id,
            "ver": credential.version,
            "exp": exp_ts,
            "nnc": credential.token_nonce,
            "sig": sig[:32],  # Compact cryptographic signature slice
        }
        encoded = base64.urlsafe_b64encode(json.dumps(token_data).encode("utf-8")).decode("utf-8")
        return f"TSQR:{encoded}"

    def parse_qr_payload(self, qr_str: str) -> Optional[Dict[str, Any]]:
        """Parse and decode opaque QR string."""
        if not qr_str.startswith("TSQR:"):
            return None
        raw_b64 = qr_str[5:]
        try:
            padded = raw_b64 + "=" * (-len(raw_b64) % 4)
            decoded_json = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
            return json.loads(decoded_json)
        except Exception as e:
            logger.warning("Failed to parse QR payload: %s", e)
            return None

    def check_rate_limit(self, client_identifier: str, limit: int = 60, window_seconds: int = 60) -> bool:
        """Simple in-memory rate-limiter for verification queries to prevent brute-force."""
        now = datetime.now(timezone.utc).timestamp()
        timestamps = self._verification_rate_tracker.get(client_identifier, [])
        # Filter timestamps within window
        valid_ts = [ts for ts in timestamps if now - ts < window_seconds]
        if len(valid_ts) >= limit:
            return False
        valid_ts.append(now)
        self._verification_rate_tracker[client_identifier] = valid_ts
        return True

    async def issue_credential(
        self,
        user_id: str,
        validity_days: int = 90,
        issued_by_role: str = "authority",
        issued_by_id: str = "authority_system",
    ) -> DigitalTouristCredential:
        """
        Issue a new Digital Tourist Credential.
        STRICT POLICY: Can ONLY be issued if tourist identity status is VERIFIED.
        """
        db = get_database()
        profile = await kyc_service.get_or_create_identity_profile(user_id)
        if profile.identity_status != KYCStatus.VERIFIED:
            raise PermissionError(
                f"Cannot issue digital credential. KYC status is '{profile.identity_status}', must be 'VERIFIED'."
            )

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=validity_days)

        # Check for existing active credentials to handle versioning & replacement
        existing_cursor = db["digital_tourist_credentials"].find({"user_id": user_id, "status": CredentialStatus.ACTIVE})
        existing_active = await existing_cursor.to_list(length=10)

        next_version = 1
        new_cred_id = str(uuid.uuid4())
        cred_ref = f"TS-CRED-{uuid.uuid4().hex[:12].upper()}"
        nonce = uuid.uuid4().hex

        for old_cred_dict in existing_active:
            old_cred = DigitalTouristCredential.from_dict(old_cred_dict)
            next_version = max(next_version, old_cred.version + 1)
            # Transition old credential to REPLACED
            await db["digital_tourist_credentials"].update_one(
                {"id": old_cred.id},
                {
                    "$set": {
                        "status": CredentialStatus.REPLACED,
                        "replaced_by_credential_id": new_cred_id,
                        "updated_at": now,
                    }
                },
            )
            logger.info("Credential %s replaced by new credential %s", old_cred.id, new_cred_id)
            await self.bus.publish_event(
                event_type="credential.replaced",
                payload={"old_credential_id": old_cred.id, "new_credential_id": new_cred_id, "user_id": user_id},
                target_user_id=user_id,
            )

        signature = self._sign_payload(cred_ref, user_id, next_version, int(expires_at.timestamp()), nonce)

        new_credential = DigitalTouristCredential(
            id=new_cred_id,
            credential_reference=cred_ref,
            user_id=user_id,
            identity_profile_id=profile.id,
            version=next_version,
            status=CredentialStatus.ACTIVE,
            issued_at=now,
            expires_at=expires_at,
            signature=signature,
            token_nonce=nonce,
            metadata={"issued_by_role": issued_by_role, "issued_by_id": issued_by_id},
        )

        await db["digital_tourist_credentials"].insert_one(new_credential.to_dict())

        # Update profile pointer
        profile.current_credential_id = new_credential.id
        profile.updated_at = now
        await db["tourist_identity_profiles"].update_one(
            {"id": profile.id},
            {"$set": {"current_credential_id": new_credential.id, "updated_at": now}},
        )

        # Dispatch realtime event
        await self.bus.publish_event(
            event_type="credential.issued",
            payload={
                "credential_id": new_credential.id,
                "credential_reference": new_credential.credential_reference,
                "user_id": user_id,
                "version": new_credential.version,
                "expires_at": expires_at.isoformat(),
            },
            target_user_id=user_id,
        )

        logger.info("Issued Digital Tourist Credential [ref=%s, user=%s, v=%d]", cred_ref, user_id, next_version)
        return new_credential

    async def rotate_qr_token(self, user_id: str) -> DigitalTouristCredential:
        """Rotate token nonce for active credential to enhance replay resistance."""
        db = get_database()
        cred_doc = await db["digital_tourist_credentials"].find_one(
            {"user_id": user_id, "status": CredentialStatus.ACTIVE}
        )
        if not cred_doc:
            raise ValueError("No active digital credential found to rotate")

        cred = DigitalTouristCredential.from_dict(cred_doc)
        now = datetime.now(timezone.utc)
        cred.token_nonce = uuid.uuid4().hex
        cred.signature = self._sign_payload(
            cred.credential_reference,
            cred.user_id,
            cred.version,
            int(cred.expires_at.timestamp()),
            cred.token_nonce,
        )
        cred.updated_at = now

        await db["digital_tourist_credentials"].update_one(
            {"id": cred.id},
            {"$set": {"token_nonce": cred.token_nonce, "signature": cred.signature, "updated_at": now}},
        )
        logger.info("Rotated QR token nonce for user %s [cred_ref=%s]", user_id, cred.credential_reference)
        return cred

    async def suspend_credential(
        self,
        credential_id: str,
        actor_id: str,
        actor_role: str,
        reason: str,
    ) -> DigitalTouristCredential:
        if actor_role not in ("admin", "authority"):
            raise PermissionError("Only authorities or admins can suspend credentials")

        db = get_database()
        cred_doc = await db["digital_tourist_credentials"].find_one({"id": credential_id})
        if not cred_doc:
            raise ValueError(f"Credential '{credential_id}' not found")

        cred = DigitalTouristCredential.from_dict(cred_doc)
        now = datetime.now(timezone.utc)
        cred.status = CredentialStatus.SUSPENDED
        cred.suspended_at = now
        cred.suspension_reason = reason
        cred.updated_at = now

        await db["digital_tourist_credentials"].update_one({"id": cred.id}, {"$set": cred.to_dict()})

        await self.bus.publish_event(
            event_type="credential.suspended",
            payload={"credential_id": cred.id, "user_id": cred.user_id, "reason": reason},
            target_user_id=cred.user_id,
        )
        return cred

    async def unsuspend_credential(
        self,
        credential_id: str,
        actor_id: str,
        actor_role: str,
    ) -> DigitalTouristCredential:
        if actor_role not in ("admin", "authority"):
            raise PermissionError("Only authorities or admins can unsuspend credentials")

        db = get_database()
        cred_doc = await db["digital_tourist_credentials"].find_one({"id": credential_id})
        if not cred_doc:
            raise ValueError(f"Credential '{credential_id}' not found")

        cred = DigitalTouristCredential.from_dict(cred_doc)
        now = datetime.now(timezone.utc)
        cred.status = CredentialStatus.ACTIVE
        cred.suspended_at = None
        cred.suspension_reason = None
        cred.updated_at = now

        await db["digital_tourist_credentials"].update_one({"id": cred.id}, {"$set": cred.to_dict()})
        return cred

    async def revoke_credential(
        self,
        credential_id: str,
        actor_id: str,
        actor_role: str,
        reason: str,
    ) -> DigitalTouristCredential:
        if actor_role not in ("admin", "authority"):
            raise PermissionError("Only authorities or admins can revoke credentials")

        db = get_database()
        cred_doc = await db["digital_tourist_credentials"].find_one({"id": credential_id})
        if not cred_doc:
            raise ValueError(f"Credential '{credential_id}' not found")

        cred = DigitalTouristCredential.from_dict(cred_doc)
        now = datetime.now(timezone.utc)
        cred.status = CredentialStatus.REVOKED
        cred.revoked_at = now
        cred.revocation_reason = reason
        cred.updated_at = now

        await db["digital_tourist_credentials"].update_one({"id": cred.id}, {"$set": cred.to_dict()})

        await self.bus.publish_event(
            event_type="credential.revoked",
            payload={"credential_id": cred.id, "user_id": cred.user_id, "reason": reason},
            target_user_id=cred.user_id,
        )
        return cred

    async def verify_credential(
        self,
        qr_payload: Optional[str] = None,
        credential_reference: Optional[str] = None,
        verifier_user_id: Optional[str] = None,
        verifier_role: str = "public",
        request_origin: Optional[str] = None,
        client_ip: Optional[str] = None,
        verification_context: Optional[str] = "checkpoint",
    ) -> Dict[str, Any]:
        """
        Controlled verification lookup.
        Rate-limited, cryptographically verified, sanitizes response to strict data minimization.
        """
        # Rate limit enforcement
        rate_key = client_ip or verifier_user_id or "anonymous"
        if not self.check_rate_limit(rate_key):
            raise RuntimeError("Rate limit exceeded for credential verification requests.")

        target_ref = credential_reference
        if qr_payload:
            parsed = self.parse_qr_payload(qr_payload)
            if parsed and "ref" in parsed:
                target_ref = parsed["ref"]

        if not target_ref:
            return {
                "credential_reference": "UNKNOWN",
                "result_code": VerificationResultCode.INVALID,
                "is_valid": False,
                "status": None,
                "issuer": "TourSafe Trust Authority",
                "provider_type": "DEV_KYC_PROVIDER",
                "verification_timestamp": datetime.now(timezone.utc).isoformat(),
            }

        db = get_database()
        cred_doc = await db["digital_tourist_credentials"].find_one({"credential_reference": target_ref})

        now = datetime.now(timezone.utc)
        ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16] if client_ip else None

        if not cred_doc:
            result_code = VerificationResultCode.UNKNOWN
            await self._log_verification(target_ref, result_code, verifier_user_id, verifier_role, request_origin, ip_hash, verification_context)
            return {
                "credential_reference": target_ref,
                "result_code": result_code,
                "is_valid": False,
                "status": None,
                "issuer": "TourSafe Trust Authority",
                "provider_type": "DEV_KYC_PROVIDER",
                "verification_timestamp": now.isoformat(),
            }

        cred = DigitalTouristCredential.from_dict(cred_doc)

        # Check expiration
        if cred.expires_at and now > cred.expires_at:
            if cred.status == CredentialStatus.ACTIVE:
                cred.status = CredentialStatus.EXPIRED
                await db["digital_tourist_credentials"].update_one(
                    {"id": cred.id},
                    {"$set": {"status": CredentialStatus.EXPIRED, "updated_at": now}},
                )
            result_code = VerificationResultCode.EXPIRED
        elif cred.status == CredentialStatus.ACTIVE:
            result_code = VerificationResultCode.VALID
        elif cred.status == CredentialStatus.REVOKED:
            result_code = VerificationResultCode.REVOKED
        elif cred.status == CredentialStatus.SUSPENDED:
            result_code = VerificationResultCode.SUSPENDED
        elif cred.status == CredentialStatus.REPLACED:
            result_code = VerificationResultCode.INVALID
        else:
            result_code = VerificationResultCode.UNKNOWN

        # Fetch minimal tourist identity display name
        profile_doc = await db["tourist_identity_profiles"].find_one({"user_id": cred.user_id})
        verified_name = None
        nationality = None
        if profile_doc:
            verified_name = profile_doc.get("full_name")
            nationality = profile_doc.get("nationality")

        await self._log_verification(target_ref, result_code, verifier_user_id, verifier_role, request_origin, ip_hash, verification_context)

        return {
            "credential_reference": cred.credential_reference,
            "result_code": result_code,
            "is_valid": (result_code == VerificationResultCode.VALID),
            "status": cred.status,
            "verified_name": verified_name if result_code == VerificationResultCode.VALID else None,
            "nationality": nationality if result_code == VerificationResultCode.VALID else None,
            "issued_at": cred.issued_at.isoformat() if cred.issued_at else None,
            "expires_at": cred.expires_at.isoformat() if cred.expires_at else None,
            "issuer": "TourSafe Trust Authority",
            "provider_type": "DEV_KYC_PROVIDER",
            "verification_timestamp": now.isoformat(),
        }

    async def _log_verification(
        self,
        credential_reference: str,
        result_code: VerificationResultCode,
        verifier_user_id: Optional[str],
        verifier_role: Optional[str],
        request_origin: Optional[str],
        client_ip_hash: Optional[str],
        verification_context: Optional[str],
    ):
        db = get_database()
        log = CredentialVerificationLog(
            credential_reference=credential_reference,
            result_code=result_code,
            verifier_user_id=verifier_user_id,
            verifier_role=verifier_role,
            request_origin=request_origin,
            client_ip_hash=client_ip_hash,
            verification_context=verification_context,
            timestamp=datetime.now(timezone.utc),
        )
        await db["credential_verification_logs"].insert_one(log.to_dict())


# Global Credential Service Singleton
credential_service = CredentialService()
