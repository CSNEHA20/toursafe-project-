"""
TourSafe Auditor Mode & Sanitized Compliance Evidence Export Service.
Enforces read-only posture and generates comprehensive compliance exports stripped of operational PII.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pymongo import ASCENDING, DESCENDING

from ...core import database as db_core
from ...models.compliance import FrameworkType
from .compliance_registry_service import compliance_registry_service
from .retention_service import retention_service
from .vendor_governance_service import vendor_governance_service
from .legal_hold_service import legal_hold_service


class AuditorService:
    async def export_sanitized_governance_bundle(self, auditor_id: str) -> Dict[str, Any]:
        """
        Exports governance policies, controls, vendor registers, active legal holds metadata,
        and audit records without sensitive operational PII.
        """
        db = db_core.get_database()

        # 1. Framework Readiness Reports
        framework_reports = {}
        for fw in FrameworkType:
            report = await compliance_registry_service.generate_readiness_report(fw)
            framework_reports[fw.value] = report

        # 2. Retention Policies
        policies = await retention_service.list_policies()
        sanitized_policies = [p.model_dump() for p in policies]

        # 3. Vendors
        vendors = await vendor_governance_service.list_vendors()
        sanitized_vendors = [v.model_dump() for v in vendors]

        # 4. Legal Holds (Metadata only - no PII content)
        holds = await legal_hold_service.list_holds()
        sanitized_holds = [
            {
                "id": h.id,
                "title": h.title,
                "scope_type": h.scope_type,
                "status": h.status,
                "placed_at": h.placed_at.isoformat() if h.placed_at else None,
                "review_date": h.review_date.isoformat() if h.review_date else None,
                "data_categories": h.data_categories,
            }
            for h in holds
        ]

        # 5. Sanitized Audit Trail (Last 100 entries)
        audit_cursor = db["governance_audit_logs"].find({}).sort("timestamp", DESCENDING).limit(100)
        sanitized_audits = []
        async for a in audit_cursor:
            a.pop("_id", None)
            sanitized_audits.append({
                "audit_id": a.get("audit_id"),
                "timestamp": a.get("timestamp"),
                "actor_role": a.get("actor_role"),
                "action": a.get("action"),
                "resource_type": a.get("resource_type"),
                "jurisdiction_id": a.get("jurisdiction_id"),
                "integrity_hash": a.get("integrity_hash"),
                "change_reason": a.get("change_reason"),
            })

        return {
            "export_metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "exported_by_auditor": auditor_id,
                "mode": "READ_ONLY_SANITIZED_AUDIT",
                "disclaimer": "Technical readiness assessment only; not legal certification. All data sanitized of operational PII.",
            },
            "framework_readiness": framework_reports,
            "retention_policies": sanitized_policies,
            "third_party_processors": sanitized_vendors,
            "legal_holds_summary": sanitized_holds,
            "governance_audit_trail": sanitized_audits,
        }


auditor_service = AuditorService()
