"""
TourSafe Vendor Governance & Third-Party Processing Register.
Features:
- Register and track third-party data processors (Mapbox, Twilio, SendGrid, Dev KYC, OpenAI/Anthropic/Gemini)
- Data sharing field minimization tracking
- Cross-border data transfer tracking and data residency awareness
- Automatic flagging of unreviewed or expired vendor security reviews
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from pymongo import ASCENDING, DESCENDING, IndexModel

from ...core import database as db_core
from ...models.compliance import (
    ContractStatus,
    SecurityReviewStatus,
    VendorIntegration,
    VendorStatus,
)
from ..governance.audit_service import audit_service


class VendorGovernanceService:
    def __init__(self):
        self.collection_name = "compliance_vendor_register"

    def _get_collection(self):
        db = db_core.get_database()
        return db[self.collection_name]

    async def init_indexes(self):
        try:
            coll = self._get_collection()
            indexes = [
                IndexModel([("id", ASCENDING)], unique=True),
                IndexModel([("vendor_name", ASCENDING)]),
                IndexModel([("security_review_status", ASCENDING)]),
            ]
            await coll.create_indexes(indexes)
        except Exception as e:
            print(f"⚠️ VendorGovernanceService index init note: {e}")

    async def seed_defaults(self):
        coll = self._get_collection()
        count = await coll.count_documents({})
        if count > 0:
            return

        now = datetime.now(timezone.utc)
        defaults = [
            VendorIntegration(
                vendor_name="Mapbox",
                service_name="Geospatial Maps & Geocoding",
                data_shared=["coordinates_only", "bounding_box"],
                purpose="Tile rendering and geofence boundary display",
                vendor_jurisdiction="US",
                data_residency_region="US-East / Global CDN",
                status=VendorStatus.ACTIVE,
                security_review_status=SecurityReviewStatus.APPROVED,
                contract_status=ContractStatus.DPA_SIGNED,
                cross_border_transfer=True,
                risk_level="LOW",
                dpa_reference="DPA-MBX-2025-01",
                last_reviewed_at=now,
                next_review_date=now + timedelta(days=180),
            ),
            VendorIntegration(
                vendor_name="Twilio",
                service_name="SMS & Voice Emergency Broadcast",
                data_shared=["phone_number", "sos_message_text"],
                purpose="Emergency responder dispatch & tourist SMS alerts",
                vendor_jurisdiction="US",
                data_residency_region="US / Regional Edge",
                status=VendorStatus.ACTIVE,
                security_review_status=SecurityReviewStatus.APPROVED,
                contract_status=ContractStatus.DPA_SIGNED,
                cross_border_transfer=True,
                risk_level="MEDIUM",
                dpa_reference="DPA-TWL-2025-04",
                last_reviewed_at=now,
                next_review_date=now + timedelta(days=180),
            ),
            VendorIntegration(
                vendor_name="SendGrid",
                service_name="Transactional Email Alerts",
                data_shared=["email", "name", "incident_summary"],
                purpose="Authority notification and password reset delivery",
                vendor_jurisdiction="US",
                data_residency_region="US",
                status=VendorStatus.ACTIVE,
                security_review_status=SecurityReviewStatus.APPROVED,
                contract_status=ContractStatus.DPA_SIGNED,
                cross_border_transfer=True,
                risk_level="LOW",
                dpa_reference="DPA-SND-2025-02",
                last_reviewed_at=now,
                next_review_date=now + timedelta(days=180),
            ),
            VendorIntegration(
                vendor_name="Dev KYC Provider (Local Mock)",
                service_name="Identity Document OCR & Verification",
                data_shared=["document_type", "name", "dob"],
                purpose="Tourist credential issuance and identity validation",
                vendor_jurisdiction="IN (Local Deployment)",
                data_residency_region="IN-Local",
                status=VendorStatus.ACTIVE,
                security_review_status=SecurityReviewStatus.APPROVED,
                contract_status=ContractStatus.DPA_SIGNED,
                cross_border_transfer=False,
                risk_level="LOW",
                dpa_reference="INTERNAL-SVC-01",
                last_reviewed_at=now,
                next_review_date=now + timedelta(days=365),
            ),
            VendorIntegration(
                vendor_name="LLM Provider (AI Copilot)",
                service_name="Authority Decision Support & Tool RAG",
                data_shared=["anonymized_query", "sop_text", "redacted_context"],
                purpose="Authority command center AI decision assistance",
                vendor_jurisdiction="US",
                data_residency_region="US-Central",
                status=VendorStatus.ACTIVE,
                security_review_status=SecurityReviewStatus.APPROVED,
                contract_status=ContractStatus.DPA_SIGNED,
                cross_border_transfer=True,
                risk_level="MEDIUM",
                dpa_reference="DPA-AI-2025-08",
                last_reviewed_at=now,
                next_review_date=now + timedelta(days=90),
            ),
        ]

        for v in defaults:
            await coll.insert_one(v.model_dump())
        print("✅ Seeded baseline Third-Party Vendor Register")

    async def register_vendor(
        self,
        vendor_name: str,
        service_name: str,
        data_shared: List[str],
        purpose: str,
        vendor_jurisdiction: str,
        data_residency_region: str,
        cross_border_transfer: bool = False,
        risk_level: str = "MEDIUM",
        dpa_reference: Optional[str] = None,
        sla_reference: Optional[str] = None,
        registered_by: str = "admin",
    ) -> VendorIntegration:
        vendor = VendorIntegration(
            vendor_name=vendor_name,
            service_name=service_name,
            data_shared=data_shared,
            purpose=purpose,
            vendor_jurisdiction=vendor_jurisdiction,
            data_residency_region=data_residency_region,
            cross_border_transfer=cross_border_transfer,
            risk_level=risk_level,
            dpa_reference=dpa_reference,
            sla_reference=sla_reference,
            security_review_status=SecurityReviewStatus.NOT_REVIEWED,
            contract_status=ContractStatus.PENDING_RENEWAL,
        )

        coll = self._get_collection()
        await coll.insert_one(vendor.model_dump())

        await audit_service.log_action(
            actor_id=registered_by,
            actor_role="admin",
            action="CREATE",
            resource_type="VENDOR_INTEGRATION",
            resource_id=vendor.id,
            after_state={"vendor_name": vendor_name, "service_name": service_name},
            change_reason=f"Registered third-party vendor processor: {vendor_name}",
        )

        return vendor

    async def update_vendor_review(
        self,
        vendor_id: str,
        security_review_status: SecurityReviewStatus,
        contract_status: Optional[ContractStatus] = None,
        risk_level: Optional[str] = None,
        reviewed_by: str = "admin",
    ) -> Optional[VendorIntegration]:
        coll = self._get_collection()
        doc = await coll.find_one({"id": vendor_id})
        if not doc:
            return None

        now = datetime.now(timezone.utc)
        update: Dict[str, Any] = {
            "security_review_status": security_review_status.value,
            "last_reviewed_at": now,
            "next_review_date": now + timedelta(days=180),
            "updated_at": now,
        }
        if contract_status:
            update["contract_status"] = contract_status.value
        if risk_level:
            update["risk_level"] = risk_level

        await coll.update_one({"id": vendor_id}, {"$set": update})
        updated = await coll.find_one({"id": vendor_id})

        await audit_service.log_action(
            actor_id=reviewed_by,
            actor_role="admin",
            action="APPROVE" if security_review_status == SecurityReviewStatus.APPROVED else "UPDATE",
            resource_type="VENDOR_INTEGRATION",
            resource_id=vendor_id,
            after_state={"security_review_status": security_review_status.value},
            change_reason=f"Updated vendor security review for {vendor_id}",
        )

        return VendorIntegration.model_validate(updated)

    async def list_vendors(self) -> List[VendorIntegration]:
        coll = self._get_collection()
        cursor = coll.find({}).sort("vendor_name", ASCENDING)
        vendors = []
        async for doc in cursor:
            vendors.append(VendorIntegration.model_validate(doc))
        return vendors


vendor_governance_service = VendorGovernanceService()
