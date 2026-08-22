from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional
import uuid

from ...core import database as db_core


def get_database():
    return db_core.get_database()
from ...models.identity import ConsentRecord, ConsentType

logger = logging.getLogger("toursafe.identity.consent")

SAFETY_IMPACT_EXPLANATIONS = {
    ConsentType.LOCATION_PROCESSING: (
        "Withdrawing location processing will disable real-time geofence alerting and automatic boundary hazard warnings."
    ),
    ConsentType.TELEMETRY_PROCESSING: (
        "Withdrawing telemetry processing will disable automated fall detection, crash detection, and anomaly alerts."
    ),
    ConsentType.CREDENTIAL_SHARING: (
        "Withdrawing credential sharing will prevent offline QR scanning by authorized checkpoint authorities."
    ),
    ConsentType.IDENTITY_VERIFICATION: (
        "Withdrawing identity verification consent will pause your active digital tourist credential issuance."
    ),
    ConsentType.DOCUMENT_PROCESSING: (
        "Withdrawing document processing consent will cancel pending KYC document validation."
    ),
}


class ConsentService:
    """
    Granular versioned user consent management.
    Ensures explicit opt-in, non-bundled checkboxes, and auditable withdrawal.
    """

    async def grant_consent(
        self,
        user_id: str,
        consent_type: ConsentType,
        version: str = "v1.0",
        source: str = "tourist_app",
        ip_address: Optional[str] = None,
    ) -> ConsentRecord:
        db = get_database()
        now = datetime.now(timezone.utc)

        # Check existing active consent
        existing = await db["user_consents"].find_one({
            "user_id": user_id,
            "consent_type": consent_type,
            "granted": True,
        })

        if existing:
            return ConsentRecord.from_dict(existing)

        record = ConsentRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            consent_type=consent_type,
            version=version,
            granted=True,
            source=source,
            granted_at=now,
            ip_address=ip_address,
        )
        await db["user_consents"].insert_one(record.to_dict())
        logger.info("Consent granted [user=%s, type=%s, version=%s]", user_id, consent_type, version)
        return record

    async def withdraw_consent(
        self,
        user_id: str,
        consent_type: ConsentType,
        reason: Optional[str] = None,
    ) -> Dict[str, any]:
        db = get_database()
        now = datetime.now(timezone.utc)

        result = await db["user_consents"].update_many(
            {"user_id": user_id, "consent_type": consent_type, "granted": True},
            {"$set": {"granted": False, "withdrawn_at": now, "withdrawal_reason": reason, "updated_at": now}},
        )

        impact = SAFETY_IMPACT_EXPLANATIONS.get(consent_type, "Consent withdrawn successfully.")
        logger.info("Consent withdrawn [user=%s, type=%s, matched=%d]", user_id, consent_type, result.matched_count)

        return {
            "consent_type": consent_type,
            "withdrawn": True,
            "withdrawn_at": now.isoformat(),
            "safety_impact": impact,
        }

    async def get_user_consents(self, user_id: str) -> List[ConsentRecord]:
        db = get_database()
        cursor = db["user_consents"].find({"user_id": user_id})
        docs = await cursor.to_list(length=50)
        return [ConsentRecord.from_dict(d) for d in docs]

    async def has_consent(self, user_id: str, consent_type: ConsentType) -> bool:
        db = get_database()
        doc = await db["user_consents"].find_one({"user_id": user_id, "consent_type": consent_type, "granted": True})
        return doc is not None


# Global Consent Service Singleton
consent_service = ConsentService()
