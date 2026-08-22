"""
TourSafe Compliance Registry & Framework Readiness Mapping Service.
Features:
- Standard control mappings for ISO 27001, SOC 2 Type II, GDPR, India DPDP, and NIST CSF
- Verifiable technical evidence registry linking to actual code, config, tests, and audit logs
- Gap analysis and remediation tracking
- Automated compliance readiness reports with mandatory disclaimer:
  "Technical readiness assessment only; not legal certification."
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pymongo import ASCENDING, DESCENDING, IndexModel

from ...core import database as db_core
from ...models.compliance import (
    ComplianceControl,
    ComplianceEvidence,
    ComplianceGap,
    ControlDomain,
    ControlStatus,
    FrameworkType,
)


class ComplianceRegistryService:
    def __init__(self):
        self.controls_collection = "compliance_controls"
        self.evidence_collection = "compliance_evidence"
        self.gaps_collection = "compliance_gaps"

    def _get_controls_coll(self):
        db = db_core.get_database()
        return db[self.controls_collection]

    def _get_evidence_coll(self):
        db = db_core.get_database()
        return db[self.evidence_collection]

    def _get_gaps_coll(self):
        db = db_core.get_database()
        return db[self.gaps_collection]

    async def init_indexes(self):
        try:
            c_coll = self._get_controls_coll()
            await c_coll.create_indexes([
                IndexModel([("control_id", ASCENDING), ("framework", ASCENDING)], unique=True),
                IndexModel([("framework", ASCENDING)]),
                IndexModel([("implementation_status", ASCENDING)]),
            ])

            e_coll = self._get_evidence_coll()
            await e_coll.create_indexes([
                IndexModel([("id", ASCENDING)], unique=True),
                IndexModel([("control_id", ASCENDING)]),
            ])

            g_coll = self._get_gaps_coll()
            await g_coll.create_indexes([
                IndexModel([("id", ASCENDING)], unique=True),
                IndexModel([("framework", ASCENDING)]),
            ])
        except Exception as e:
            print(f"⚠️ ComplianceRegistryService index init note: {e}")

    async def seed_defaults(self):
        coll = self._get_controls_coll()
        count = await coll.count_documents({})
        if count > 0:
            return

        controls = [
            # ISO 27001 Controls
            ComplianceControl(
                control_id="ISO-A.8.1",
                framework=FrameworkType.ISO_27001,
                domain=ControlDomain.DATA_PROTECTION,
                title="User Endpoint Devices & Telemetry Security",
                description="Controls on mobile edge telemetry ingestion, replay protection, and device health verification.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/routers/telemetry.py", "backend/tests/test_security_hardening.py"],
                owner="security_team",
            ),
            ComplianceControl(
                control_id="ISO-A.9.2",
                framework=FrameworkType.ISO_27001,
                domain=ControlDomain.ACCESS_CONTROL,
                title="User Access Provisioning & RBAC",
                description="Role-based access control, JWT authentication, and token revocation.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/routers/auth.py", "backend/app/core/security.py"],
                owner="iam_team",
            ),
            ComplianceControl(
                control_id="ISO-A.12.4",
                framework=FrameworkType.ISO_27001,
                domain=ControlDomain.AUDIT_LOGGING,
                title="Logging and Monitoring",
                description="Immutable SHA-256 cryptographic hash-chained governance and security audit logging.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/services/governance/audit_service.py"],
                owner="compliance_lead",
            ),
            ComplianceControl(
                control_id="ISO-A.17.1",
                framework=FrameworkType.ISO_27001,
                domain=ControlDomain.DISASTER_RECOVERY,
                title="Information Security Continuity",
                description="Snapshot backup automation, multi-tier health probes, circuit breakers, and database restore procedures.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/services/reliability/backup_service.py", "backend/app/routers/reliability.py"],
                owner="devops_lead",
            ),

            # SOC 2 Type II Controls
            ComplianceControl(
                control_id="SOC2-CC6.1",
                framework=FrameworkType.SOC_2,
                domain=ControlDomain.ACCESS_CONTROL,
                title="Logical Access Security",
                description="Zero-trust security core, refresh token rotation, rate limiting, and RBAC.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/core/security_middleware.py"],
                owner="security_team",
            ),
            ComplianceControl(
                control_id="SOC2-CC7.2",
                framework=FrameworkType.SOC_2,
                domain=ControlDomain.INCIDENT_RESPONSE,
                title="Security Incident Monitoring & Response",
                description="Live security event ingestion, brute-force mitigation, and SOS emergency escalation orchestrator.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/services/emergency/response_orchestrator.py"],
                owner="incident_commander",
            ),
            ComplianceControl(
                control_id="SOC2-CC8.1",
                framework=FrameworkType.SOC_2,
                domain=ControlDomain.DATA_PROTECTION,
                title="Change Management & Policy Governance",
                description="Dual-approval policy lifecycles, configuration rollback, and versioned parameter governance.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/services/governance/config_governance_service.py"],
                owner="gov_admin",
            ),

            # GDPR Readiness Controls
            ComplianceControl(
                control_id="GDPR-Art.5.1c",
                framework=FrameworkType.GDPR_READINESS,
                domain=ControlDomain.DATA_PROTECTION,
                title="Data Minimization & Location Precision",
                description="Coordinate truncation for non-emergency analytics and PII log redaction.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/core/compliance/minimization.py"],
                owner="privacy_officer",
            ),
            ComplianceControl(
                control_id="GDPR-Art.7",
                framework=FrameworkType.GDPR_READINESS,
                domain=ControlDomain.DATA_PROTECTION,
                title="Conditions for Consent",
                description="Granular unbundled consent purposes, version tracking, and instant withdrawal support.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/services/compliance/consent_service.py"],
                owner="privacy_officer",
            ),
            ComplianceControl(
                control_id="GDPR-Art.15-20",
                framework=FrameworkType.GDPR_READINESS,
                domain=ControlDomain.DATA_PROTECTION,
                title="Data Subject Rights (Access, Export, Deletion)",
                description="DSR lifecycle workflow with identity verification, portable JSON export, and safe deletion engine.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/services/compliance/privacy_request_service.py"],
                owner="privacy_officer",
            ),
            ComplianceControl(
                control_id="GDPR-Art.28",
                framework=FrameworkType.GDPR_READINESS,
                domain=ControlDomain.THIRD_PARTY_RISK,
                title="Third-Party Processor Governance",
                description="Vendor register tracking DPAs, data minimization, and cross-border data residency.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/services/compliance/vendor_governance_service.py"],
                owner="legal_lead",
            ),

            # India DPDP Readiness Controls
            ComplianceControl(
                control_id="DPDP-Sec.6",
                framework=FrameworkType.DPDP_READINESS,
                domain=ControlDomain.DATA_PROTECTION,
                title="Notice and Consent Architecture",
                description="Clear multilingual purpose specification, consent evidence hash, and consent manager integration.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/services/compliance/consent_service.py"],
                owner="dpo_india",
            ),
            ComplianceControl(
                control_id="DPDP-Sec.8.7",
                framework=FrameworkType.DPDP_READINESS,
                domain=ControlDomain.DATA_PROTECTION,
                title="Data Erasure and Retention Limitation",
                description="Automated retention engine respecting legal holds and active safety emergency constraints.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/services/compliance/retention_service.py"],
                owner="dpo_india",
            ),
            ComplianceControl(
                control_id="DPDP-Sec.12",
                framework=FrameworkType.DPDP_READINESS,
                domain=ControlDomain.DATA_PROTECTION,
                title="Right to Grievance Redressal & DSR",
                description="In-app privacy request tracking, correction workflows, and structured resolution logs.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/services/compliance/privacy_request_service.py"],
                owner="dpo_india",
            ),

            # NIST CSF Controls
            ComplianceControl(
                control_id="NIST-PR.AC-1",
                framework=FrameworkType.NIST_CSF,
                domain=ControlDomain.ACCESS_CONTROL,
                title="Identities and Credentials Management",
                description="Multi-tier RBAC, periodic access reviews, and break-glass emergency elevation.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/services/compliance/access_governance_service.py"],
                owner="iam_team",
            ),
            ComplianceControl(
                control_id="NIST-DE.AE-1",
                framework=FrameworkType.NIST_CSF,
                domain=ControlDomain.AI_ML_GOVERNANCE,
                title="Baseline Anomaly & Threat Detection",
                description="LSTM autoencoder sensor anomaly inference, rule-based safety correlation, and drift monitoring.",
                implementation_status=ControlStatus.IMPLEMENTED,
                evidence_refs=["backend/app/services/ml/engine.py", "backend/app/ml/lifecycle.py"],
                owner="ml_lead",
            ),
        ]

        for c in controls:
            await coll.insert_one(c.model_dump())

        # Seed initial compliance gaps that require external legal/policy actions
        gaps_coll = self._get_gaps_coll()
        gaps = [
            ComplianceGap(
                framework=FrameworkType.GDPR_READINESS,
                requirement="Article 27 EU Representative Appointment",
                current_state="TourSafe architecture supports GDPR technical controls and DSR workflows.",
                target_state="Designate formal EU representative if non-EU authority targets EU tourists.",
                severity="HIGH",
                owner="external_legal_counsel",
                status="REQUIRES_LEGAL_REVIEW",
            ),
            ComplianceGap(
                framework=FrameworkType.DPDP_READINESS,
                requirement="Formal Data Protection Board of India Registration",
                current_state="Consent and grievance redressal technical controls implemented.",
                target_state="Register as Significant Data Fiduciary (SDF) once operational thresholds notified.",
                severity="MEDIUM",
                owner="external_legal_counsel",
                status="REQUIRES_AUTHORITY_POLICY",
            ),
            ComplianceGap(
                framework=FrameworkType.ISO_27001,
                requirement="Third-Party Certification Audit",
                current_state="ISO 27001:2022 technical Annex A controls implemented and tested.",
                target_state="Schedule Stage 1 & Stage 2 external certification audit with accredited registrar.",
                severity="HIGH",
                owner="ciso_office",
                status="REQUIRES_AUTHORITY_POLICY",
            ),
        ]
        for g in gaps:
            await gaps_coll.insert_one(g.model_dump())

        print("✅ Seeded baseline Compliance Framework Controls & Gaps")

    async def list_controls(
        self,
        framework: Optional[FrameworkType] = None,
        domain: Optional[ControlDomain] = None,
        status: Optional[ControlStatus] = None,
    ) -> List[ComplianceControl]:
        coll = self._get_controls_coll()
        query: Dict[str, Any] = {}
        if framework:
            query["framework"] = framework.value
        if domain:
            query["domain"] = domain.value
        if status:
            query["implementation_status"] = status.value

        cursor = coll.find(query).sort("control_id", ASCENDING)
        results = []
        async for doc in cursor:
            results.append(ComplianceControl.model_validate(doc))
        return results

    async def list_gaps(self, framework: Optional[FrameworkType] = None) -> List[ComplianceGap]:
        coll = self._get_gaps_coll()
        query: Dict[str, Any] = {}
        if framework:
            query["framework"] = framework.value
        cursor = coll.find(query)
        results = []
        async for doc in cursor:
            results.append(ComplianceGap.model_validate(doc))
        return results

    async def generate_readiness_report(self, framework: FrameworkType) -> Dict[str, Any]:
        controls = await self.list_controls(framework=framework)
        gaps = await self.list_gaps(framework=framework)

        total = len(controls)
        implemented = sum(1 for c in controls if c.implementation_status == ControlStatus.IMPLEMENTED.value)
        partial = sum(1 for c in controls if c.implementation_status == ControlStatus.PARTIAL.value)
        not_impl = sum(1 for c in controls if c.implementation_status == ControlStatus.NOT_IMPLEMENTED.value)
        review = sum(1 for c in controls if c.implementation_status == ControlStatus.REQUIRES_REVIEW.value)

        percentage = round(((implemented + (partial * 0.5)) / max(1, total)) * 100, 1)

        return {
            "framework": framework.value,
            "total_controls": total,
            "implemented_count": implemented,
            "partial_count": partial,
            "not_implemented_count": not_impl,
            "requires_review_count": review,
            "readiness_percentage": percentage,
            "gaps_count": len(gaps),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Technical readiness assessment only; not legal certification. All determinations subject to formal legal review.",
            "controls_summary": [c.model_dump() for c in controls],
            "identified_gaps": [g.model_dump() for g in gaps],
        }


compliance_registry_service = ComplianceRegistryService()
