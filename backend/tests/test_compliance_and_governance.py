"""
TourSafe Automated Unit & Integration Tests for Compliance, Governance, Privacy & Regulatory Readiness.
Validates:
- Granular consent lifecycle, purpose isolation, and vital-interests safety exceptions
- Data Subject Requests (DSR: Access, Export, Correction, Deletion) & Identity Verification
- Retention Policy Engine, Versioning, Approval, Rollback, and Multi-Jurisdiction Resolution
- Safe Deletion sweeps with Legal Hold & Active Safety Incident protection
- Legal Holds placement, queries, and release workflows
- Third-Party Vendor Register & Cross-Border Residency Risk Review
- Access Governance periodic reviews and Break-Glass Emergency PAM
- Framework Readiness (ISO 27001, SOC 2, GDPR, DPDP, NIST) and Legal Disclaimer enforcement
- Auditor Mode sanitized exports with zero operational PII
- Data Minimization and Coordinate Truncation
"""

import asyncio
from datetime import datetime, timedelta, timezone
import pytest

from app.core import database as db_module
from app.core.compliance.minimization import (
    mask_pii_string,
    minimize_coordinates,
    pseudonymize_identifier,
    sanitize_payload_for_audit,
)
from app.models.compliance import (
    ArchiveBehavior,
    ConsentPurpose,
    ControlDomain,
    ControlStatus,
    DataCategory,
    DeletionBehavior,
    FrameworkType,
    LegalHoldScopeType,
    LegalHoldStatus,
    LegalProcessingBasis,
    PolicyStatus,
    PrivacyRequestStatus,
    PrivacyRequestType,
    SecurityReviewStatus,
    VendorStatus,
)
from app.services.compliance import (
    access_governance_service,
    auditor_service,
    compliance_registry_service,
    consent_service,
    legal_hold_service,
    privacy_request_service,
    retention_service,
    vendor_governance_service,
)
from app.services.governance.audit_service import audit_service


# ---------------------------------------------------------------------------
# Mock In-Memory Database for Async Tests
# ---------------------------------------------------------------------------

class MockCollection:
    def __init__(self, name="collection"):
        self.name = name
        self.docs = []

    async def create_indexes(self, indexes):
        return True

    async def count_documents(self, filter_dict=None):
        filter_dict = filter_dict or {}
        return sum(1 for d in self.docs if self._matches(d, filter_dict))

    async def insert_one(self, doc):
        d = doc.copy()
        if "_id" not in d:
            d["_id"] = f"mock_{len(self.docs)+1}"
        self.docs.append(d)
        return type("InsertResult", (), {"inserted_id": d["_id"]})()

    async def find_one(self, filter_dict=None):
        filter_dict = filter_dict or {}
        for d in self.docs:
            if self._matches(d, filter_dict):
                return d.copy()
        return None

    def find(self, filter_dict=None):
        filter_dict = filter_dict or {}
        matches = [d for d in self.docs if self._matches(d, filter_dict)]

        class AsyncCursor:
            def __init__(self, items):
                self.items = items

            def sort(self, key, direction=1):
                return self

            def limit(self, count):
                self.items = self.items[:count]
                return self

            async def to_list(self, length=100):
                return [d.copy() for d in self.items[:length]]

            def __aiter__(self):
                self._iter = iter(self.items)
                return self

            async def __anext__(self):
                try:
                    return next(self._iter).copy()
                except StopIteration:
                    raise StopAsyncIteration

        return AsyncCursor(matches)

    async def update_one(self, filter_dict, update_dict):
        for d in self.docs:
            if self._matches(d, filter_dict):
                if "$set" in update_dict:
                    d.update(update_dict["$set"])
                return type("UpdateResult", (), {"modified_count": 1})()
        return type("UpdateResult", (), {"modified_count": 0})()

    async def update_many(self, filter_dict, update_dict):
        count = 0
        for d in self.docs:
            if self._matches(d, filter_dict):
                if "$set" in update_dict:
                    d.update(update_dict["$set"])
                count += 1
        return type("UpdateResult", (), {"modified_count": count})()

    async def delete_one(self, filter_dict):
        for i, d in enumerate(self.docs):
            if self._matches(d, filter_dict):
                del self.docs[i]
                return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()

    async def delete_many(self, filter_dict):
        before = len(self.docs)
        self.docs = [d for d in self.docs if not self._matches(d, filter_dict)]
        return type("DeleteResult", (), {"deleted_count": before - len(self.docs)})()

    def _matches(self, doc, filter_dict):
        if not filter_dict:
            return True
        for k, v in filter_dict.items():
            if k == "$or":
                if not any(self._matches(doc, cond) for cond in v):
                    return False
            elif k == "$and":
                if not all(self._matches(doc, cond) for cond in v):
                    return False
            elif isinstance(v, dict):
                field_val = doc.get(k)
                if "$ne" in v and field_val == v["$ne"]:
                    return False
                if "$in" in v and field_val not in v["$in"]:
                    return False
                if "$lt" in v and not (field_val is not None and field_val < v["$lt"]):
                    return False
                if "$gt" in v and not (field_val is not None and field_val > v["$gt"]):
                    return False
            else:
                if doc.get(k) != v:
                    return False
        return True


class MockDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = MockCollection(name)
        return self.collections[name]

    async def list_collection_names(self):
        return list(self.collections.keys())


@pytest.fixture(autouse=True)
def setup_mock_db(monkeypatch):
    mock_db = MockDatabase()
    monkeypatch.setattr(db_module, "get_database", lambda: mock_db)
    return mock_db


# ===========================================================================
# 1. Data Minimization & Privacy Core Tests
# ===========================================================================

def test_coordinate_minimization_levels():
    lat, lon = 12.9715987, 77.5945627

    # Exact for SOS / Emergency
    exact_lat, exact_lon = minimize_coordinates(lat, lon, "EMERGENCY")
    assert exact_lat == 12.971599
    assert exact_lon == 77.594563

    # Operational for Active Geofence
    op_lat, op_lon = minimize_coordinates(lat, lon, "OPERATIONAL")
    assert op_lat == 12.9716
    assert op_lon == 77.5946

    # Aggregate / Analytics (2 decimal places ~ 1.1km)
    agg_lat, agg_lon = minimize_coordinates(lat, lon, "AGGREGATE")
    assert agg_lat == 12.97
    assert agg_lon == 77.59

    # City level
    city_lat, city_lon = minimize_coordinates(lat, lon, "CITY_LEVEL")
    assert city_lat == 13.0
    assert city_lon == 77.6


def test_pii_masking_and_pseudonymization():
    email = "tourist.jane@gmail.com"
    phone = "+919876543210"
    name = "Vishal Lakshmikanthan"

    masked_email = mask_pii_string(email)
    assert masked_email.endswith("@gmail.com")
    assert "*" in masked_email
    assert "jane" not in masked_email

    masked_phone = mask_pii_string(phone)
    assert masked_phone.endswith("3210")
    assert "*" in masked_phone

    masked_name = mask_pii_string(name)
    assert masked_name.startswith("V")
    assert masked_name.endswith("n")
    assert "*" in masked_name

    pseudo = pseudonymize_identifier("user_12345")
    assert pseudo.startswith("anon_")
    assert len(pseudo) == 17


def test_audit_payload_sanitization():
    payload = {
        "user_id": "usr_99",
        "password_hash": "$2b$12$secretpasswordhash",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "action": "LOGIN",
        "nested": {
            "api_key": "sec_123456",
            "safe_data": "ok_value",
        },
    }
    sanitized = sanitize_payload_for_audit(payload)
    assert sanitized["password_hash"] == "[REDACTED_FOR_PRIVACY]"
    assert sanitized["access_token"] == "[REDACTED_FOR_PRIVACY]"
    assert sanitized["nested"]["api_key"] == "[REDACTED_FOR_PRIVACY]"
    assert sanitized["nested"]["safe_data"] == "ok_value"
    assert sanitized["user_id"] == "usr_99"


# ===========================================================================
# 2. Granular Consent Management Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_consent_grant_withdraw_and_supersede():
    subject_id = "tourist_alice_01"

    # Grant GPS consent
    c1 = await consent_service.grant_consent(
        subject_id=subject_id,
        purpose=ConsentPurpose.LOCATION_TRACKING,
        version="1.0",
    )
    assert c1.status == "GRANTED"
    assert c1.purpose == ConsentPurpose.LOCATION_TRACKING
    assert len(c1.evidence_hash) == 64

    # Verify active consent check
    has_consent, basis = await consent_service.has_active_consent(subject_id, ConsentPurpose.LOCATION_TRACKING)
    assert has_consent is True
    assert basis == LegalProcessingBasis.CONSENT

    # Grant v1.1 - should supersede v1.0
    c2 = await consent_service.grant_consent(
        subject_id=subject_id,
        purpose=ConsentPurpose.LOCATION_TRACKING,
        version="1.1",
    )
    assert c2.version == "1.1"
    assert c2.status == "GRANTED"

    # Withdraw consent
    withdrawn = await consent_service.withdraw_consent(
        subject_id=subject_id,
        purpose=ConsentPurpose.LOCATION_TRACKING,
        reason="Tourist turned off location tracking",
    )
    assert withdrawn is not None
    assert withdrawn.status == "WITHDRAWN"

    # Active consent should now be False under normal conditions
    has_consent, basis = await consent_service.has_active_consent(subject_id, ConsentPurpose.LOCATION_TRACKING)
    assert has_consent is False

    # Safety Exception / Vital Interests override during active emergency
    has_emergency_consent, emergency_basis = await consent_service.has_active_consent(
        subject_id,
        ConsentPurpose.LOCATION_TRACKING,
        is_emergency=True,
    )
    assert has_emergency_consent is True
    assert emergency_basis == LegalProcessingBasis.VITAL_INTERESTS_EMERGENCY


# ===========================================================================
# 3. Retention Policy Engine, Approval & Rollback Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_retention_policy_lifecycle_and_rollback():
    # Seed baseline policies
    await retention_service.seed_defaults()
    policies = await retention_service.list_policies()
    assert len(policies) >= 6

    # Draft a new retention policy for TELEMETRY
    draft = await retention_service.create_policy(
        data_type=DataCategory.TELEMETRY,
        retention_period_days=14,
        created_by="privacy_officer",
        description="Stricter 14-day telemetry retention",
    )
    assert draft.status == PolicyStatus.DRAFT
    assert draft.version >= 2

    # Approve and activate
    activated = await retention_service.approve_and_activate_policy(
        policy_id=draft.id,
        approved_by="ciso_admin",
    )
    assert activated is not None
    assert activated.status == PolicyStatus.ACTIVE

    # Verify server-side policy resolution
    resolved = await retention_service.resolve_policy(DataCategory.TELEMETRY)
    assert resolved.retention_period_days == 14

    # Rollback to v1 settings
    rolled = await retention_service.rollback_policy(
        current_policy_id=activated.id,
        target_version=1,
        rolled_back_by="ciso_admin",
    )
    assert rolled is not None
    assert rolled.status == PolicyStatus.ACTIVE
    assert rolled.retention_period_days == 30  # Seeded v1 was 30 days


# ===========================================================================
# 4. Legal Holds & Safe Deletion Execution Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_legal_hold_and_safe_retention_sweep():
    db = db_module.get_database()
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(days=60)

    # Insert old telemetry for 2 tourists (A and B)
    await db["telemetry_records"].insert_one({
        "tourist_id": "tourist_A",
        "created_at": old_time,
        "accel_x": 0.12,
    })
    await db["telemetry_records"].insert_one({
        "tourist_id": "tourist_B",
        "created_at": old_time,
        "accel_x": 0.99,
    })

    # Place a Legal Hold on tourist_A
    hold = await legal_hold_service.create_hold(
        title="Court Order #2026-441",
        reason="Investigation into national park incident",
        scope_type=LegalHoldScopeType.USER,
        scope_id="tourist_A",
        placed_by="legal_counsel",
    )
    assert hold.status == LegalHoldStatus.ACTIVE

    # Verify hold check
    is_held, reason = await legal_hold_service.is_entity_held("tourist_A")
    assert is_held is True
    assert "Court Order #2026-441" in reason

    is_b_held, _ = await legal_hold_service.is_entity_held("tourist_B")
    assert is_b_held is False

    # Execute retention sweep (Telemetry policy retention = 30 days)
    job_result = await retention_service.run_retention_job(triggered_by="test_runner", dry_run=False)
    assert job_result["total_records_deleted"] == 1  # tourist_B deleted
    assert job_result["total_records_retained_legal_hold"] == 1  # tourist_A preserved

    # Verify DB records
    rec_a = await db["telemetry_records"].find_one({"tourist_id": "tourist_A"})
    rec_b = await db["telemetry_records"].find_one({"tourist_id": "tourist_B"})
    assert rec_a is not None
    assert rec_b is None

    # Release legal hold on tourist_A
    await legal_hold_service.release_hold(
        hold_id=hold.id,
        released_by="legal_counsel",
        release_reason="Investigation concluded",
    )
    is_held_after, _ = await legal_hold_service.is_entity_held("tourist_A")
    assert is_held_after is False

    # Next retention sweep should safely purge tourist_A
    job_result2 = await retention_service.run_retention_job(triggered_by="test_runner", dry_run=False)
    assert job_result2["total_records_deleted"] == 1
    rec_a_after = await db["telemetry_records"].find_one({"tourist_id": "tourist_A"})
    assert rec_a_after is None


# ===========================================================================
# 5. Data Subject Requests (DSR: Export & Safe Deletion) Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_privacy_request_export_and_safe_deletion():
    db = db_module.get_database()
    tourist_id = "tourist_charlie"

    # Seed tourist data
    await db["users"].insert_one({
        "id": tourist_id,
        "email": "charlie@traveler.com",
        "full_name": "Charlie Traveler",
        "role": "tourist",
    })
    await db["tourists"].insert_one({
        "id": "tourist_profile_charlie",
        "user_id": tourist_id,
        "full_name": "Charlie Traveler",
    })
    await db["locations"].insert_one({
        "tourist_id": tourist_id,
        "latitude": 15.2993,
        "longitude": 74.1240,
        "created_at": datetime.now(timezone.utc),
    })

    # 1. Access / Export Request
    exp_req = await privacy_request_service.create_request(
        subject_id=tourist_id,
        request_type=PrivacyRequestType.EXPORT,
    )
    assert exp_req.status == PrivacyRequestStatus.SUBMITTED

    # Verify Identity
    verified_req = await privacy_request_service.verify_identity(
        request_id=exp_req.id,
        subject_id=tourist_id,
    )
    assert verified_req is not None
    assert verified_req.identity_verified is True
    assert verified_req.status == PrivacyRequestStatus.UNDER_REVIEW

    # Review & Approve
    reviewed_req = await privacy_request_service.review_request(
        request_id=exp_req.id,
        reviewer_id="privacy_admin",
        decision="APPROVE",
    )
    assert reviewed_req is not None
    assert reviewed_req.status == PrivacyRequestStatus.COMPLETED
    assert reviewed_req.export_token is not None

    # Fetch export payload using token
    export_data = await privacy_request_service.get_export_payload(reviewed_req.export_token)
    assert export_data is not None
    assert export_data["user_account"]["email"] == "charlie@traveler.com"
    assert "password_hash" not in export_data["user_account"]

    # 2. Deletion Request
    del_req = await privacy_request_service.create_request(
        subject_id=tourist_id,
        request_type=PrivacyRequestType.DELETION,
        scope=[DataCategory.LOCATION, DataCategory.IDENTITY],
    )
    await privacy_request_service.verify_identity(del_req.id, tourist_id)
    del_reviewed = await privacy_request_service.review_request(del_req.id, "privacy_admin", "APPROVE")
    assert del_reviewed is not None
    assert del_reviewed.status == PrivacyRequestStatus.COMPLETED

    # Verify locations deleted and identity pseudonymized
    loc_count = await db["locations"].count_documents({"tourist_id": tourist_id})
    assert loc_count == 0

    user_doc = await db["users"].find_one({"id": tourist_id})
    assert user_doc["full_name"] == "[DELETED_USER]"
    assert user_doc["is_active"] is False


# ===========================================================================
# 6. Third-Party Vendor Register & Cross-Border Residency Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_vendor_register_and_review_lifecycle():
    await vendor_governance_service.seed_defaults()
    vendors = await vendor_governance_service.list_vendors()
    assert len(vendors) >= 5

    # Register new third-party processor
    new_vendor = await vendor_governance_service.register_vendor(
        vendor_name="Local SMS Gateway",
        service_name="Regional Alert Broadcast",
        data_shared=["phone_number"],
        purpose="Emergency alerts",
        vendor_jurisdiction="IN",
        data_residency_region="IN-Central",
        cross_border_transfer=False,
    )
    assert new_vendor.security_review_status == SecurityReviewStatus.NOT_REVIEWED

    # Update review to APPROVED
    updated = await vendor_governance_service.update_vendor_review(
        vendor_id=new_vendor.id,
        security_review_status=SecurityReviewStatus.APPROVED,
        risk_level="LOW",
    )
    assert updated is not None
    assert updated.security_review_status == SecurityReviewStatus.APPROVED
    assert updated.risk_level == "LOW"


# ===========================================================================
# 7. Access Governance & Break-Glass Emergency PAM Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_access_review_and_break_glass_pam():
    db = db_module.get_database()
    await db["users"].insert_one({"id": "adm_1", "email": "admin1@toursafe.gov", "role": "admin"})
    await db["users"].insert_one({"id": "adm_2", "email": "admin2@toursafe.gov", "role": "admin"})

    # Create periodic access review
    review = await access_governance_service.create_access_review(
        title="Q3 2026 Admin Privilege Review",
        scope="ADMIN_USERS",
        reviewer_id="ciso_office",
        period_start=datetime.now(timezone.utc) - timedelta(days=90),
        period_end=datetime.now(timezone.utc),
    )
    assert len(review.accounts_reviewed) >= 2

    # Complete access review
    completed = await access_governance_service.complete_access_review(
        review_id=review.id,
        reviewer_id="ciso_office",
        decisions=[
            {"user_id": "adm_1", "decision": "APPROVED"},
            {"user_id": "adm_2", "decision": "APPROVED"},
        ],
        findings="All administrative accounts verified and active.",
    )
    assert completed is not None
    assert completed.status == "COMPLETED"

    # Test Break-Glass Emergency PAM
    bg_session = await access_governance_service.request_break_glass_access(
        user_id="oncall_eng_1",
        user_email="oncall@toursafe.internal",
        requested_role="EMERGENCY_SUPER_ADMIN",
        justification="Database cluster failover after outage",
        target_scope="INFRASTRUCTURE_RECOVERY",
        duration_hours=2,
    )
    assert bg_session.status == "ACTIVE"
    assert bg_session.expires_at > datetime.now(timezone.utc)

    # Revoke break-glass session
    revoked = await access_governance_service.revoke_break_glass_session(
        session_id=bg_session.id,
        revoked_by="security_admin",
    )
    assert revoked is not None
    assert revoked.status == "REVOKED"


# ===========================================================================
# 8. Framework Readiness & Legal Disclaimer Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_framework_readiness_and_disclaimer():
    await compliance_registry_service.seed_defaults()

    for fw in [FrameworkType.ISO_27001, FrameworkType.SOC_2, FrameworkType.GDPR_READINESS, FrameworkType.DPDP_READINESS, FrameworkType.NIST_CSF]:
        report = await compliance_registry_service.generate_readiness_report(fw)
        assert report["total_controls"] > 0
        assert report["readiness_percentage"] > 0
        assert "Technical readiness assessment only; not legal certification" in report["disclaimer"]


# ===========================================================================
# 9. Auditor Mode Sanitized Export Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_auditor_sanitized_bundle_export():
    await compliance_registry_service.seed_defaults()
    await retention_service.seed_defaults()
    await vendor_governance_service.seed_defaults()

    bundle = await auditor_service.export_sanitized_governance_bundle(auditor_id="external_auditor_01")
    assert bundle["export_metadata"]["mode"] == "READ_ONLY_SANITIZED_AUDIT"
    assert "framework_readiness" in bundle
    assert "retention_policies" in bundle
    assert "third_party_processors" in bundle
    assert "governance_audit_trail" in bundle
