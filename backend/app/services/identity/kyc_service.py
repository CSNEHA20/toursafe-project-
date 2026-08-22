from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from ...core import database as db_core


def get_database():
    return db_core.get_database()
from ...models.identity import (
    KYCDocumentRecord,
    KYCDocumentType,
    KYCRejectionReason,
    KYCStatus,
    KYCVerificationHistory,
    TouristIdentityProfile,
)
from ..realtime_bus import RealtimeEventBus
from .document_storage import document_storage_service
from .provider_base import provider_registry

logger = logging.getLogger("toursafe.identity.kyc")

KYC_PERMISSIONS = {
    "admin": {"KYC_VIEW", "KYC_REVIEW", "KYC_APPROVE", "KYC_REJECT", "KYC_ADMIN"},
    "authority": {"KYC_VIEW", "KYC_REVIEW", "KYC_APPROVE", "KYC_REJECT"},
    "responder": set(),
    "tourist": set(),
}


class KYCService:
    """
    Core KYC Lifecycle and Review Management Service.
    Coordinates document submissions, provider verification, reviewer decisions, and audit history.
    """

    def __init__(self, bus: Optional[RealtimeEventBus] = None):
        self.bus = bus or RealtimeEventBus()
        self.provider_registry = provider_registry
        self.storage = document_storage_service

    def check_permission(self, role: str, required_permission: str) -> bool:
        user_perms = KYC_PERMISSIONS.get(role, set())
        return required_permission in user_perms or "KYC_ADMIN" in user_perms

    async def get_or_create_identity_profile(self, user_id: str, full_name: Optional[str] = None) -> TouristIdentityProfile:
        db = get_database()
        doc = await db["tourist_identity_profiles"].find_one({"user_id": user_id})
        if doc:
            return TouristIdentityProfile.from_dict(doc)

        # Fallback to User or Tourist collection for profile bootstrap
        name = full_name or "Tourist Traveler"
        user_doc = await db["users"].find_one({"id": user_id})
        if user_doc and user_doc.get("full_name"):
            name = user_doc["full_name"]
        else:
            tourist_doc = await db["tourists"].find_one({"user_id": user_id})
            if tourist_doc and tourist_doc.get("full_name"):
                name = tourist_doc["full_name"]

        profile = TouristIdentityProfile(
            id=str(uuid.uuid4()),
            user_id=user_id,
            full_name=name,
            identity_status=KYCStatus.NOT_STARTED,
        )
        await db["tourist_identity_profiles"].insert_one(profile.to_dict())
        logger.info("Created new TouristIdentityProfile [id=%s, user_id=%s]", profile.id, user_id)
        return profile

    async def start_kyc(self, user_id: str) -> TouristIdentityProfile:
        db = get_database()
        profile = await self.get_or_create_identity_profile(user_id)

        if profile.identity_status in (KYCStatus.VERIFIED, KYCStatus.UNDER_REVIEW):
            return profile

        previous_status = profile.identity_status
        profile.identity_status = KYCStatus.PENDING
        profile.updated_at = datetime.now(timezone.utc)

        await db["tourist_identity_profiles"].update_one(
            {"id": profile.id},
            {"$set": {"identity_status": profile.identity_status, "updated_at": profile.updated_at}},
        )

        # Record audit history
        await self._record_history(
            identity_profile_id=profile.id,
            tourist_id=user_id,
            previous_status=str(previous_status),
            new_status=str(profile.identity_status),
            actor_id=user_id,
            actor_role="tourist",
            action="START_KYC",
            reason="Tourist initiated KYC verification workflow",
        )

        return profile

    async def submit_document(
        self,
        user_id: str,
        document_type: KYCDocumentType,
        masked_identifier: str,
        issuing_country: Optional[str] = None,
        storage_key: Optional[str] = None,
        file_size_bytes: int = 1024,
        mime_type: str = "application/pdf",
        provider_name: Optional[str] = None,
    ) -> KYCDocumentRecord:
        db = get_database()
        profile = await self.get_or_create_identity_profile(user_id)

        # Secure storage check
        if not storage_key:
            storage_key = self.storage.store_document_metadata(
                tourist_id=user_id,
                document_type=str(document_type),
                mime_type=mime_type,
                file_size_bytes=file_size_bytes,
            )

        provider = self.provider_registry.get_provider(provider_name)
        provider_resp = await provider.submit_verification(
            tourist_id=user_id,
            document_type=document_type,
            masked_identifier=masked_identifier,
            storage_key=storage_key,
        )

        doc_record = KYCDocumentRecord(
            id=str(uuid.uuid4()),
            tourist_id=user_id,
            identity_profile_id=profile.id,
            document_type=document_type,
            issuing_country=issuing_country,
            masked_identifier=masked_identifier,
            storage_key=storage_key,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
            verification_status=KYCStatus.UNDER_REVIEW,
            provider=provider.provider_name,
            provider_reference=provider_resp.get("provider_reference"),
            submitted_at=datetime.now(timezone.utc),
        )
        await db["kyc_documents"].insert_one(doc_record.to_dict())

        previous_status = profile.identity_status
        profile.identity_status = KYCStatus.UNDER_REVIEW
        profile.updated_at = datetime.now(timezone.utc)
        await db["tourist_identity_profiles"].update_one(
            {"id": profile.id},
            {"$set": {"identity_status": profile.identity_status, "updated_at": profile.updated_at}},
        )

        # Record audit history
        await self._record_history(
            identity_profile_id=profile.id,
            tourist_id=user_id,
            document_id=doc_record.id,
            previous_status=str(previous_status),
            new_status=str(KYCStatus.UNDER_REVIEW),
            actor_id=user_id,
            actor_role="tourist",
            action="SUBMIT_DOCUMENT",
            reason=f"Submitted {document_type} document for review",
            provider_reference=doc_record.provider_reference,
        )

        # Dispatch realtime event
        await self.bus.publish_event(
            event_type="kyc.submitted",
            payload={
                "tourist_id": user_id,
                "identity_profile_id": profile.id,
                "document_id": doc_record.id,
                "document_type": str(document_type),
                "status": str(KYCStatus.UNDER_REVIEW),
                "provider": provider.provider_name,
            },
            channel="authority:operations",
        )

        return doc_record

    async def assign_reviewer(
        self,
        document_id: str,
        reviewer_id: str,
        reviewer_role: str,
    ) -> KYCDocumentRecord:
        if not self.check_permission(reviewer_role, "KYC_REVIEW"):
            raise PermissionError("Insufficient authority permissions to assign KYC review")

        db = get_database()
        doc_dict = await db["kyc_documents"].find_one({"id": document_id})
        if not doc_dict:
            raise ValueError(f"KYC document '{document_id}' not found")

        doc = KYCDocumentRecord.from_dict(doc_dict)
        doc.reviewer_id = reviewer_id
        doc.reviewed_at = datetime.now(timezone.utc)
        doc.updated_at = datetime.now(timezone.utc)

        await db["kyc_documents"].update_one(
            {"id": doc.id},
            {"$set": {"reviewer_id": doc.reviewer_id, "reviewed_at": doc.reviewed_at, "updated_at": doc.updated_at}},
        )

        await self._record_history(
            identity_profile_id=doc.identity_profile_id or "",
            tourist_id=doc.tourist_id,
            document_id=doc.id,
            previous_status=str(doc.verification_status),
            new_status=str(doc.verification_status),
            actor_id=reviewer_id,
            actor_role=reviewer_role,
            action="ASSIGN_REVIEWER",
            reason=f"Assigned reviewer {reviewer_id}",
        )

        return doc

    async def approve_kyc(
        self,
        document_id: str,
        reviewer_id: str,
        reviewer_role: str,
        notes: Optional[str] = None,
        verified_fields: Optional[List[str]] = None,
        validity_days: int = 365,
    ) -> Tuple[KYCDocumentRecord, TouristIdentityProfile]:
        if not self.check_permission(reviewer_role, "KYC_APPROVE"):
            raise PermissionError("Insufficient authority permissions to approve KYC")

        db = get_database()
        doc_dict = await db["kyc_documents"].find_one({"id": document_id})
        if not doc_dict:
            raise ValueError(f"KYC document '{document_id}' not found")

        doc = KYCDocumentRecord.from_dict(doc_dict)
        profile = await self.get_or_create_identity_profile(doc.tourist_id)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=validity_days)

        # Update document
        doc.verification_status = KYCStatus.VERIFIED
        doc.verified_at = now
        doc.expires_at = expires_at
        doc.reviewer_id = reviewer_id
        doc.reviewer_notes = notes
        doc.updated_at = now

        await db["kyc_documents"].update_one({"id": doc.id}, {"$set": doc.to_dict()})

        # Update identity profile
        previous_status = profile.identity_status
        profile.identity_status = KYCStatus.VERIFIED
        profile.verified_fields = verified_fields or ["full_name", "date_of_birth", "nationality"]
        profile.last_verified_at = now
        profile.verification_expires_at = expires_at
        profile.updated_at = now

        await db["tourist_identity_profiles"].update_one({"id": profile.id}, {"$set": profile.to_dict()})

        # Also sync to existing Tourist record if present
        await db["tourists"].update_one(
            {"user_id": doc.tourist_id},
            {"$set": {"kyc_status": "verified", "identity_verified_at": now}},
        )

        # Record audit history
        await self._record_history(
            identity_profile_id=profile.id,
            tourist_id=doc.tourist_id,
            document_id=doc.id,
            previous_status=str(previous_status),
            new_status=str(KYCStatus.VERIFIED),
            actor_id=reviewer_id,
            actor_role=reviewer_role,
            action="APPROVE_KYC",
            reason=notes or "Document verification approved by authority operator",
            provider_reference=doc.provider_reference,
        )

        # Dispatch realtime event
        await self.bus.publish_event(
            event_type="kyc.approved",
            payload={
                "tourist_id": doc.tourist_id,
                "identity_profile_id": profile.id,
                "document_id": doc.id,
                "status": "VERIFIED",
                "verified_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
            },
            target_user_id=doc.tourist_id,
        )

        logger.info("KYC Approved for tourist %s [profile_id=%s, reviewer=%s]", doc.tourist_id, profile.id, reviewer_id)
        return doc, profile

    async def reject_kyc(
        self,
        document_id: str,
        reviewer_id: str,
        reviewer_role: str,
        reason: KYCRejectionReason,
        details: Optional[str] = None,
        internal_notes: Optional[str] = None,
    ) -> Tuple[KYCDocumentRecord, TouristIdentityProfile]:
        if not self.check_permission(reviewer_role, "KYC_REJECT"):
            raise PermissionError("Insufficient authority permissions to reject KYC")

        db = get_database()
        doc_dict = await db["kyc_documents"].find_one({"id": document_id})
        if not doc_dict:
            raise ValueError(f"KYC document '{document_id}' not found")

        doc = KYCDocumentRecord.from_dict(doc_dict)
        profile = await self.get_or_create_identity_profile(doc.tourist_id)

        now = datetime.now(timezone.utc)
        doc.verification_status = KYCStatus.REJECTED
        doc.rejection_reason = reason
        doc.rejection_details = details
        doc.reviewer_notes = internal_notes
        doc.reviewer_id = reviewer_id
        doc.reviewed_at = now
        doc.updated_at = now

        await db["kyc_documents"].update_one({"id": doc.id}, {"$set": doc.to_dict()})

        previous_status = profile.identity_status
        profile.identity_status = KYCStatus.REJECTED
        profile.updated_at = now

        await db["tourist_identity_profiles"].update_one({"id": profile.id}, {"$set": profile.to_dict()})

        # Sync to tourist collection
        await db["tourists"].update_one(
            {"user_id": doc.tourist_id},
            {"$set": {"kyc_status": "rejected"}},
        )

        await self._record_history(
            identity_profile_id=profile.id,
            tourist_id=doc.tourist_id,
            document_id=doc.id,
            previous_status=str(previous_status),
            new_status=str(KYCStatus.REJECTED),
            actor_id=reviewer_id,
            actor_role=reviewer_role,
            action="REJECT_KYC",
            reason=f"Rejected due to {reason}: {details or ''}",
            provider_reference=doc.provider_reference,
        )

        await self.bus.publish_event(
            event_type="kyc.rejected",
            payload={
                "tourist_id": doc.tourist_id,
                "identity_profile_id": profile.id,
                "document_id": doc.id,
                "status": "REJECTED",
                "reason": str(reason),
                "details": details,
            },
            target_user_id=doc.tourist_id,
        )

        logger.info("KYC Rejected for tourist %s [reason=%s, reviewer=%s]", doc.tourist_id, reason, reviewer_id)
        return doc, profile

    async def request_action(
        self,
        document_id: str,
        reviewer_id: str,
        reviewer_role: str,
        instructions: str,
        internal_notes: Optional[str] = None,
    ) -> Tuple[KYCDocumentRecord, TouristIdentityProfile]:
        if not self.check_permission(reviewer_role, "KYC_REVIEW"):
            raise PermissionError("Insufficient authority permissions to request KYC action")

        db = get_database()
        doc_dict = await db["kyc_documents"].find_one({"id": document_id})
        if not doc_dict:
            raise ValueError(f"KYC document '{document_id}' not found")

        doc = KYCDocumentRecord.from_dict(doc_dict)
        profile = await self.get_or_create_identity_profile(doc.tourist_id)

        now = datetime.now(timezone.utc)
        doc.verification_status = KYCStatus.REQUIRES_ACTION
        doc.requires_action_instructions = instructions
        doc.reviewer_notes = internal_notes
        doc.reviewer_id = reviewer_id
        doc.reviewed_at = now
        doc.updated_at = now

        await db["kyc_documents"].update_one({"id": doc.id}, {"$set": doc.to_dict()})

        previous_status = profile.identity_status
        profile.identity_status = KYCStatus.REQUIRES_ACTION
        profile.updated_at = now

        await db["tourist_identity_profiles"].update_one({"id": profile.id}, {"$set": profile.to_dict()})

        await self._record_history(
            identity_profile_id=profile.id,
            tourist_id=doc.tourist_id,
            document_id=doc.id,
            previous_status=str(previous_status),
            new_status=str(KYCStatus.REQUIRES_ACTION),
            actor_id=reviewer_id,
            actor_role=reviewer_role,
            action="REQUEST_ACTION",
            reason=f"Action required: {instructions}",
            provider_reference=doc.provider_reference,
        )

        await self.bus.publish_event(
            event_type="kyc.requires_action",
            payload={
                "tourist_id": doc.tourist_id,
                "identity_profile_id": profile.id,
                "document_id": doc.id,
                "status": "REQUIRES_ACTION",
                "instructions": instructions,
            },
            target_user_id=doc.tourist_id,
        )

        return doc, profile

    async def expire_verification(self, identity_profile_id: str) -> Optional[TouristIdentityProfile]:
        db = get_database()
        doc = await db["tourist_identity_profiles"].find_one({"id": identity_profile_id})
        if not doc:
            return None

        profile = TouristIdentityProfile.from_dict(doc)
        if profile.identity_status != KYCStatus.VERIFIED:
            return profile

        now = datetime.now(timezone.utc)
        previous_status = profile.identity_status
        profile.identity_status = KYCStatus.EXPIRED
        profile.updated_at = now

        await db["tourist_identity_profiles"].update_one({"id": profile.id}, {"$set": profile.to_dict()})

        await self._record_history(
            identity_profile_id=profile.id,
            tourist_id=profile.user_id,
            previous_status=str(previous_status),
            new_status=str(KYCStatus.EXPIRED),
            actor_id="system",
            actor_role="system",
            action="EXPIRE_VERIFICATION",
            reason="Configured verification validity window elapsed",
        )

        await self.bus.publish_event(
            event_type="kyc.expired",
            payload={"tourist_id": profile.user_id, "identity_profile_id": profile.id, "status": "EXPIRED"},
            target_user_id=profile.user_id,
        )

        return profile

    async def _record_history(
        self,
        identity_profile_id: str,
        tourist_id: str,
        previous_status: str,
        new_status: str,
        actor_id: str,
        actor_role: str,
        action: str,
        reason: Optional[str] = None,
        document_id: Optional[str] = None,
        provider_reference: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> KYCVerificationHistory:
        db = get_database()
        history = KYCVerificationHistory(
            id=str(uuid.uuid4()),
            identity_profile_id=identity_profile_id,
            tourist_id=tourist_id,
            document_id=document_id,
            previous_status=previous_status,
            new_status=new_status,
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            reason=reason,
            provider_reference=provider_reference,
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc),
        )
        await db["kyc_verification_history"].insert_one(history.to_dict())
        return history


# Global KYC Service Singleton
kyc_service = KYCService()
