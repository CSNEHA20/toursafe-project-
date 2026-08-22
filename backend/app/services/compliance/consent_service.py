"""
TourSafe Granular Consent Management Service.
Features:
- Granular consent tracking per purpose (Location, Telemetry, KYC, Comms, Analytics, Personalization)
- Consent versioning and evidence hash calculation
- Consent withdrawal lifecycle
- Safety exception / Vital interests emergency processing override
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pymongo import ASCENDING, DESCENDING, IndexModel

from ...core import database as db_core
from ...models.compliance import (
    ConsentPurpose,
    ConsentRecord,
    LegalProcessingBasis,
)
from ..governance.audit_service import audit_service


class ConsentService:
    def __init__(self):
        self.collection_name = "compliance_consents"

    def _get_collection(self):
        db = db_core.get_database()
        return db[self.collection_name]

    async def init_indexes(self):
        try:
            coll = self._get_collection()
            indexes = [
                IndexModel([("id", ASCENDING)], unique=True),
                IndexModel([("subject_id", ASCENDING), ("purpose", ASCENDING), ("status", ASCENDING)]),
                IndexModel([("granted_at", DESCENDING)]),
            ]
            await coll.create_indexes(indexes)
        except Exception as e:
            print(f"⚠️ ConsentService index init note: {e}")

    def _generate_evidence_hash(self, subject_id: str, purpose: str, version: str, timestamp: str) -> str:
        payload = f"{subject_id}:{purpose}:{version}:{timestamp}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def grant_consent(
        self,
        subject_id: str,
        purpose: ConsentPurpose,
        version: str = "1.0",
        source: str = "MOBILE_APP",
        jurisdiction_id: Optional[str] = None,
        legal_basis: LegalProcessingBasis = LegalProcessingBasis.CONSENT,
    ) -> ConsentRecord:
        coll = self._get_collection()
        now = datetime.now(timezone.utc)
        evidence_hash = self._generate_evidence_hash(subject_id, purpose.value, version, now.isoformat())

        # Supersede existing active consent for the same purpose
        await coll.update_many(
            {"subject_id": subject_id, "purpose": purpose.value, "status": "GRANTED"},
            {"$set": {"status": "SUPERSEDED", "withdrawn_at": now, "updated_at": now}},
        )

        record = ConsentRecord(
            subject_id=subject_id,
            purpose=purpose,
            version=version,
            status="GRANTED",
            granted_at=now,
            source=source,
            jurisdiction_id=jurisdiction_id,
            legal_basis=legal_basis,
            evidence_hash=evidence_hash,
        )

        await coll.insert_one(record.model_dump())

        await audit_service.log_action(
            actor_id=subject_id,
            actor_role="tourist",
            action="CREATE",
            resource_type="CONSENT_RECORD",
            resource_id=record.id,
            after_state={"purpose": purpose.value, "version": version, "status": "GRANTED", "legal_basis": legal_basis.value},
            change_reason=f"Granted consent for purpose: {purpose.value}",
        )

        return record

    async def withdraw_consent(
        self,
        subject_id: str,
        purpose: ConsentPurpose,
        reason: Optional[str] = None,
    ) -> Optional[ConsentRecord]:
        coll = self._get_collection()
        now = datetime.now(timezone.utc)

        doc = await coll.find_one({"subject_id": subject_id, "purpose": purpose.value, "status": "GRANTED"})
        if not doc:
            return None

        await coll.update_one(
            {"id": doc["id"]},
            {"$set": {"status": "WITHDRAWN", "withdrawn_at": now, "updated_at": now}},
        )

        updated_doc = await coll.find_one({"id": doc["id"]})

        await audit_service.log_action(
            actor_id=subject_id,
            actor_role="tourist",
            action="REVOKE",
            resource_type="CONSENT_RECORD",
            resource_id=doc["id"],
            after_state={"status": "WITHDRAWN", "withdrawn_at": now.isoformat()},
            change_reason=f"Withdrew consent for purpose: {purpose.value} (Reason: {reason or 'User choice'})",
        )

        return ConsentRecord.model_validate(updated_doc)

    async def get_subject_consents(self, subject_id: str) -> List[ConsentRecord]:
        coll = self._get_collection()
        cursor = coll.find({"subject_id": subject_id}).sort("granted_at", DESCENDING)
        consents = []
        async for doc in cursor:
            consents.append(ConsentRecord.model_validate(doc))
        return consents

    async def has_active_consent(
        self,
        subject_id: str,
        purpose: ConsentPurpose,
        is_emergency: bool = False,
    ) -> Tuple[bool, LegalProcessingBasis]:
        """
        Evaluates whether data processing is authorized.
        If an active emergency is declared and purpose is essential for safety,
        authorizes under VITAL_INTERESTS_EMERGENCY without violating privacy policy.
        """
        if is_emergency and purpose in (ConsentPurpose.LOCATION_TRACKING, ConsentPurpose.EMERGENCY_COMMUNICATION):
            return True, LegalProcessingBasis.VITAL_INTERESTS_EMERGENCY

        coll = self._get_collection()
        doc = await coll.find_one({"subject_id": subject_id, "purpose": purpose.value, "status": "GRANTED"})
        if doc:
            return True, LegalProcessingBasis.CONSENT
        return False, LegalProcessingBasis.CONSENT


consent_service = ConsentService()
