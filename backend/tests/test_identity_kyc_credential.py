import copy
from datetime import datetime, timedelta, timezone
import json
import pytest
import sys
import uuid
from typing import Any, Dict, List, Optional
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, "backend")

from app.main import app
import app.core.database as db_module
from app.core.security import create_access_token
from app.models.identity import (
    ConsentType,
    CredentialStatus,
    KYCDocumentType,
    KYCRejectionReason,
    KYCStatus,
    ProviderStatus,
    VerificationResultCode,
)
from app.services.identity import (
    consent_service,
    credential_service,
    document_storage_service,
    identity_service,
    kyc_service,
    provider_registry,
    DevKYCProvider,
)
from app.schemas.identity import (
    TouristIdentityProfileUpdate,
    KYCDocumentSubmitRequest,
    KYCApproveRequest,
    KYCRejectRequest,
    KYCRequestActionRequest,
    CredentialIssueRequest,
    CredentialRevokeRequest,
    CredentialSuspendRequest,
    CredentialVerifyRequest,
    ConsentGrantRequest,
    ConsentWithdrawRequest,
)


class MockCollection:
    def __init__(self, name="collection"):
        self.name = name
        self.docs: List[Dict[str, Any]] = []

    def _matches(self, doc: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
        for k, v in filter_dict.items():
            if k == "$or":
                if not any(self._matches(doc, sub) for sub in v):
                    return False
            elif isinstance(v, dict):
                val = doc.get(k)
                if "$in" in v:
                    if val not in v["$in"]:
                        return False
                elif "$gte" in v:
                    if str(val) < v["$gte"]:
                        return False
                elif "$lte" in v:
                    if str(val) > v["$lte"]:
                        return False
                elif "$regex" in v:
                    import re
                    pattern = re.compile(v["$regex"], re.IGNORECASE if v.get("$options") == "i" else 0)
                    if not pattern.search(str(val or "")):
                        return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    async def insert_one(self, doc):
        d = copy.deepcopy(doc)
        if "_id" not in d:
            d["_id"] = f"mock_{len(self.docs)+1}"
        self.docs.append(d)
        return type("InsertResult", (), {"inserted_id": d["_id"]})()

    async def find_one(self, filter_dict=None, sort=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        matches = [d for d in self.docs if self._matches(d, filter_dict)]
        if not matches:
            return None
        if sort:
            sort_field, sort_order = sort[0]
            matches.sort(key=lambda x: x.get(sort_field, ""), reverse=(sort_order == -1))
        return copy.deepcopy(matches[0])

    def find(self, filter_dict=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        matches = [copy.deepcopy(d) for d in self.docs if self._matches(d, filter_dict)]

        class AsyncCursor:
            def __init__(self, items):
                self.items = items
                self.index = 0

            def sort(self, key, order=1):
                self.items.sort(key=lambda x: x.get(key, "") if x.get(key) is not None else "", reverse=(order == -1))
                return self

            def skip(self, n):
                self.items = self.items[n:]
                return self

            def limit(self, n):
                self.items = self.items[:n]
                return self

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index < len(self.items):
                    item = self.items[self.index]
                    self.index += 1
                    return item
                raise StopAsyncIteration

            async def to_list(self, length=100):
                return self.items[:length]

        return AsyncCursor(matches)

    async def count_documents(self, filter_dict=None):
        filter_dict = filter_dict or {}
        return sum(1 for d in self.docs if self._matches(d, filter_dict))

    async def update_one(self, filter_dict, update_dict, upsert=False):
        filter_dict = filter_dict or {}
        for d in self.docs:
            if self._matches(d, filter_dict):
                if "$set" in update_dict:
                    d.update(copy.deepcopy(update_dict["$set"]))
                return type("UpdateResult", (), {"matched_count": 1, "modified_count": 1})()
        if upsert:
            new_doc = copy.deepcopy(filter_dict)
            if "$set" in update_dict:
                new_doc.update(copy.deepcopy(update_dict["$set"]))
            self.docs.append(new_doc)
            return type("UpdateResult", (), {"matched_count": 0, "upserted_id": "new_1"})()
        return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0})()

    async def update_many(self, filter_dict, update_dict):
        filter_dict = filter_dict or {}
        matched = 0
        for d in self.docs:
            if self._matches(d, filter_dict):
                matched += 1
                if "$set" in update_dict:
                    d.update(copy.deepcopy(update_dict["$set"]))
        return type("UpdateResult", (), {"matched_count": matched, "modified_count": matched})()

    async def delete_one(self, filter_dict):
        filter_dict = filter_dict or {}
        for i, d in enumerate(self.docs):
            if self._matches(d, filter_dict):
                self.docs.pop(i)
                return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()


class MockDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = MockCollection(name)
        return self.collections[name]

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return self[name]


@pytest.fixture(autouse=True)
def mock_db_fixture(monkeypatch):
    mock_db = MockDatabase()
    import app.core.database as d_mod
    monkeypatch.setattr(d_mod, "get_database", lambda: mock_db)
    monkeypatch.setattr(d_mod, "database", mock_db)
    return mock_db


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_tourist_auth():
    tourist_id = f"test-tourist-{uuid.uuid4().hex[:8]}"
    token = create_access_token(user_id=tourist_id, role="tourist")
    return tourist_id, token


@pytest.fixture
def mock_tourist_b_auth():
    tourist_id = f"test-tourist-b-{uuid.uuid4().hex[:8]}"
    token = create_access_token(user_id=tourist_id, role="tourist")
    return tourist_id, token


@pytest.fixture
def mock_authority_auth():
    auth_id = f"test-authority-{uuid.uuid4().hex[:8]}"
    token = create_access_token(user_id=auth_id, role="authority")
    return auth_id, token


@pytest.fixture
def mock_admin_auth():
    admin_id = f"test-admin-{uuid.uuid4().hex[:8]}"
    token = create_access_token(user_id=admin_id, role="admin")
    return admin_id, token


@pytest.fixture
def mock_responder_auth():
    resp_id = f"test-responder-{uuid.uuid4().hex[:8]}"
    token = create_access_token(user_id=resp_id, role="responder")
    return resp_id, token


@pytest.mark.asyncio
class TestIdentityProfileAndDataMinimization:
    """Test Tourist Identity Profile separation and sanitized views."""

    async def test_identity_profile_creation_and_self_view(self, mock_tourist_auth):
        tourist_id, token = mock_tourist_auth
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get(
                "/api/v1/identity/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["user_id"] == tourist_id
            assert data["identity_status"] == KYCStatus.NOT_STARTED
            assert "verified_fields" in data
            assert data["documents_count"] == 0

    async def test_identity_profile_update_and_reverification_trigger(self, mock_tourist_auth, mock_authority_auth):
        tourist_id, t_token = mock_tourist_auth
        auth_id, a_token = mock_authority_auth

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Start KYC and Submit Document
            await ac.post("/api/v1/kyc/start", headers={"Authorization": f"Bearer {t_token}"})
            doc_res = await ac.post(
                "/api/v1/kyc/documents",
                headers={"Authorization": f"Bearer {t_token}"},
                json={
                    "document_type": "PASSPORT",
                    "issuing_country": "CAN",
                    "masked_identifier": "•••• 9876",
                },
            )
            doc_id = doc_res.json()["id"]

            # 2. Authority approves KYC
            await ac.post(
                f"/api/v1/authority/kyc/{doc_id}/approve",
                headers={"Authorization": f"Bearer {a_token}"},
                json={"notes": "All verified", "verified_fields": ["full_name", "nationality"]},
            )

            # Issue credential
            cred_res = await ac.post(
                f"/api/v1/credentials/issue/{tourist_id}",
                headers={"Authorization": f"Bearer {a_token}"},
                json={"validity_days": 60},
            )
            assert cred_res.status_code == 201

            # Verify active status
            status_res = await ac.get("/api/v1/identity/status", headers={"Authorization": f"Bearer {t_token}"})
            assert status_res.json()["identity_status"] == "VERIFIED"

            # 3. Update sensitive verified field (full_name)
            update_res = await ac.patch(
                "/api/v1/identity/me",
                headers={"Authorization": f"Bearer {t_token}"},
                json={"full_name": "Updated Name After Marriage"},
            )
            assert update_res.status_code == 200
            # Status should be downgraded to UNDER_REVIEW for safety
            assert update_res.json()["identity_status"] == KYCStatus.UNDER_REVIEW

    async def test_responder_view_data_minimization(self, mock_tourist_auth):
        tourist_id, _ = mock_tourist_auth
        resp_view = await identity_service.get_responder_view(tourist_id)
        assert resp_view.user_id == tourist_id
        # Verify responder view does NOT contain raw KYC documents, national IDs, or trust scores
        view_dict = resp_view.model_dump()
        assert "document_summaries" not in view_dict
        assert "trust_score" not in view_dict
        assert "risk_score" not in view_dict


@pytest.mark.asyncio
class TestKYCWorkflowAndReview:
    """Test full KYC lifecycle, review assignment, rejection reasons, and requires-action."""

    async def test_full_kyc_approval_lifecycle(self, mock_tourist_auth, mock_authority_auth):
        tourist_id, t_token = mock_tourist_auth
        auth_id, a_token = mock_authority_auth

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Start KYC
            start_res = await ac.post("/api/v1/kyc/start", headers={"Authorization": f"Bearer {t_token}"})
            assert start_res.status_code == 200
            assert start_res.json()["identity_status"] == KYCStatus.PENDING

            # 2. Submit Document
            doc_res = await ac.post(
                "/api/v1/kyc/documents",
                headers={"Authorization": f"Bearer {t_token}"},
                json={
                    "document_type": "PASSPORT",
                    "issuing_country": "FRA",
                    "masked_identifier": "•••• 1234",
                    "file_size_bytes": 2048,
                    "mime_type": "application/pdf",
                },
            )
            assert doc_res.status_code == 201
            doc_data = doc_res.json()
            doc_id = doc_data["id"]
            assert doc_data["verification_status"] == KYCStatus.UNDER_REVIEW
            assert doc_data["masked_identifier"] == "•••• 1234"

            # 3. Authority lists pending queue
            pending_res = await ac.get("/api/v1/authority/kyc/pending", headers={"Authorization": f"Bearer {a_token}"})
            assert pending_res.status_code == 200
            pending_ids = [d["id"] for d in pending_res.json()["items"]]
            assert doc_id in pending_ids

            # 4. Authority inspects detail with preview URL
            detail_res = await ac.get(f"/api/v1/authority/kyc/{doc_id}", headers={"Authorization": f"Bearer {a_token}"})
            assert detail_res.status_code == 200
            assert detail_res.json()["preview_url"] is not None

            # 5. Authority approves
            approve_res = await ac.post(
                f"/api/v1/authority/kyc/{doc_id}/approve",
                headers={"Authorization": f"Bearer {a_token}"},
                json={"notes": "Passports verified", "validity_days": 180},
            )
            assert approve_res.status_code == 200
            assert approve_res.json()["status"] == "APPROVED"

            # 6. Verify history audit trail
            hist_res = await ac.get("/api/v1/kyc/history", headers={"Authorization": f"Bearer {t_token}"})
            assert hist_res.status_code == 200
            history = hist_res.json()
            assert len(history) >= 2
            actions = [h["action"] for h in history]
            assert "SUBMIT_DOCUMENT" in actions
            assert "APPROVE_KYC" in actions

    async def test_kyc_rejection_with_structured_reason(self, mock_tourist_auth, mock_authority_auth):
        tourist_id, t_token = mock_tourist_auth
        auth_id, a_token = mock_authority_auth

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            await ac.post("/api/v1/kyc/start", headers={"Authorization": f"Bearer {t_token}"})
            doc_res = await ac.post(
                "/api/v1/kyc/documents",
                headers={"Authorization": f"Bearer {t_token}"},
                json={
                    "document_type": "DRIVING_LICENSE",
                    "masked_identifier": "•••• 5555",
                },
            )
            doc_id = doc_res.json()["id"]

            # Reject
            reject_res = await ac.post(
                f"/api/v1/authority/kyc/{doc_id}/reject",
                headers={"Authorization": f"Bearer {a_token}"},
                json={
                    "reason": "DOCUMENT_UNREADABLE",
                    "details": "Image resolution too blurry to read expiry date.",
                    "internal_notes": "Suspected camera blur.",
                },
            )
            assert reject_res.status_code == 200
            assert reject_res.json()["status"] == "REJECTED"

            # Tourist status is now REJECTED
            status_res = await ac.get("/api/v1/identity/status", headers={"Authorization": f"Bearer {t_token}"})
            assert status_res.json()["identity_status"] == KYCStatus.REJECTED

    async def test_kyc_request_action_and_resubmission(self, mock_tourist_auth, mock_authority_auth):
        tourist_id, t_token = mock_tourist_auth
        auth_id, a_token = mock_authority_auth

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            await ac.post("/api/v1/kyc/start", headers={"Authorization": f"Bearer {t_token}"})
            doc_res = await ac.post(
                "/api/v1/kyc/documents",
                headers={"Authorization": f"Bearer {t_token}"},
                json={"document_type": "NATIONAL_ID", "masked_identifier": "•••• 3333"},
            )
            doc_id = doc_res.json()["id"]

            # Request action
            req_res = await ac.post(
                f"/api/v1/authority/kyc/{doc_id}/request-action",
                headers={"Authorization": f"Bearer {a_token}"},
                json={"instructions": "Please submit a clear color scan of the back of your ID card."},
            )
            assert req_res.status_code == 200
            assert req_res.json()["status"] == "REQUIRES_ACTION"

            # Tourist sees instructions
            doc_detail = await ac.get(f"/api/v1/kyc/documents/{doc_id}", headers={"Authorization": f"Bearer {t_token}"})
            assert doc_detail.json()["verification_status"] == "REQUIRES_ACTION"
            assert "back of your ID card" in doc_detail.json()["requires_action_instructions"]


@pytest.mark.asyncio
class TestDigitalTouristCredentialLifecycle:
    """Test Credential Issuance gates, Cryptographic QR, Versioning, Replacement, Revocation, and Suspension."""

    async def test_cannot_issue_credential_if_not_verified(self, mock_tourist_auth, mock_authority_auth):
        tourist_id, _ = mock_tourist_auth
        auth_id, a_token = mock_authority_auth

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post(
                f"/api/v1/credentials/issue/{tourist_id}",
                headers={"Authorization": f"Bearer {a_token}"},
                json={"validity_days": 30},
            )
            assert res.status_code == 400
            assert "must be 'VERIFIED'" in res.json()["detail"]

    async def test_credential_issuance_versioning_and_replacement(self, mock_tourist_auth, mock_authority_auth):
        tourist_id, t_token = mock_tourist_auth
        auth_id, a_token = mock_authority_auth

        # Manually prepare verified profile
        profile = await kyc_service.get_or_create_identity_profile(tourist_id)
        profile.identity_status = KYCStatus.VERIFIED
        db = db_module.get_database()
        await db["tourist_identity_profiles"].update_one(
            {"id": profile.id},
            {"$set": {"identity_status": KYCStatus.VERIFIED}},
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Issue Credential v1
            v1_res = await ac.post(
                f"/api/v1/credentials/issue/{tourist_id}",
                headers={"Authorization": f"Bearer {a_token}"},
                json={"validity_days": 30},
            )
            assert v1_res.status_code == 201
            v1_data = v1_res.json()
            assert v1_data["version"] == 1
            assert v1_data["status"] == CredentialStatus.ACTIVE
            assert v1_data["qr_payload"].startswith("TSQR:")

            v1_ref = v1_data["credential_reference"]
            v1_qr = v1_data["qr_payload"]

            # 2. Verify v1 is VALID
            verify_v1 = await ac.post("/api/v1/credentials/verify", json={"qr_payload": v1_qr})
            assert verify_v1.status_code == 200
            assert verify_v1.json()["result_code"] == "VALID"
            assert verify_v1.json()["is_valid"] is True

            # 3. Issue Credential v2 (should replace v1)
            v2_res = await ac.post(
                f"/api/v1/credentials/issue/{tourist_id}",
                headers={"Authorization": f"Bearer {a_token}"},
                json={"validity_days": 60},
            )
            assert v2_res.status_code == 201
            v2_data = v2_res.json()
            assert v2_data["version"] == 2
            assert v2_data["status"] == CredentialStatus.ACTIVE

            # 4. Verification of old v1 should now return INVALID (Replaced)
            verify_old_v1 = await ac.post("/api/v1/credentials/verify", json={"qr_payload": v1_qr})
            assert verify_old_v1.status_code == 200
            assert verify_old_v1.json()["result_code"] == "INVALID"
            assert verify_old_v1.json()["is_valid"] is False

            # 5. Verification of v2 should return VALID
            verify_v2 = await ac.post("/api/v1/credentials/verify", json={"qr_payload": v2_data["qr_payload"]})
            assert verify_v2.status_code == 200
            assert verify_v2.json()["result_code"] == "VALID"
            assert verify_v2.json()["is_valid"] is True

    async def test_credential_suspension_and_revocation(self, mock_tourist_auth, mock_authority_auth):
        tourist_id, t_token = mock_tourist_auth
        auth_id, a_token = mock_authority_auth

        # Bootstrap verified profile
        profile = await kyc_service.get_or_create_identity_profile(tourist_id)
        profile.identity_status = KYCStatus.VERIFIED
        db = db_module.get_database()
        await db["tourist_identity_profiles"].update_one(
            {"id": profile.id},
            {"$set": {"identity_status": KYCStatus.VERIFIED}},
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Issue
            cred_res = await ac.post(
                f"/api/v1/credentials/issue/{tourist_id}",
                headers={"Authorization": f"Bearer {a_token}"},
                json={"validity_days": 30},
            )
            cred_id = cred_res.json()["id"]
            qr_payload = cred_res.json()["qr_payload"]

            # 1. Suspend
            susp_res = await ac.post(
                f"/api/v1/credentials/{cred_id}/suspend",
                headers={"Authorization": f"Bearer {a_token}"},
                json={"reason": "Suspected passport report loss"},
            )
            assert susp_res.status_code == 200
            assert susp_res.json()["status"] == CredentialStatus.SUSPENDED

            # Check QR verification returns SUSPENDED
            v_susp = await ac.post("/api/v1/credentials/verify", json={"qr_payload": qr_payload})
            assert v_susp.json()["result_code"] == "SUSPENDED"
            assert v_susp.json()["is_valid"] is False

            # 2. Unsuspend
            unsusp_res = await ac.post(
                f"/api/v1/credentials/{cred_id}/unsuspend",
                headers={"Authorization": f"Bearer {a_token}"},
            )
            assert unsusp_res.status_code == 200
            assert unsusp_res.json()["status"] == CredentialStatus.ACTIVE

            # 3. Revoke
            rev_res = await ac.post(
                f"/api/v1/credentials/{cred_id}/revoke",
                headers={"Authorization": f"Bearer {a_token}"},
                json={"reason": "Tourist requested account closure"},
            )
            assert rev_res.status_code == 200
            assert rev_res.json()["status"] == CredentialStatus.REVOKED

            # Check QR verification returns REVOKED
            v_rev = await ac.post("/api/v1/credentials/verify", json={"qr_payload": qr_payload})
            assert v_rev.json()["result_code"] == "REVOKED"
            assert v_rev.json()["is_valid"] is False

    async def test_qr_token_rotation(self, mock_tourist_auth, mock_authority_auth):
        tourist_id, t_token = mock_tourist_auth
        auth_id, a_token = mock_authority_auth

        # Bootstrap verified
        profile = await kyc_service.get_or_create_identity_profile(tourist_id)
        profile.identity_status = KYCStatus.VERIFIED
        db = db_module.get_database()
        await db["tourist_identity_profiles"].update_one(
            {"id": profile.id},
            {"$set": {"identity_status": KYCStatus.VERIFIED}},
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            cred_res = await ac.post(
                f"/api/v1/credentials/issue/{tourist_id}",
                headers={"Authorization": f"Bearer {a_token}"},
                json={"validity_days": 30},
            )
            initial_nonce = cred_res.json()["token_nonce"]

            rotate_res = await ac.post("/api/v1/credentials/me/rotate-qr", headers={"Authorization": f"Bearer {t_token}"})
            assert rotate_res.status_code == 200
            assert rotate_res.json()["token_nonce"] != initial_nonce


@pytest.mark.asyncio
class TestSecurityAndIsolation:
    """Test cross-user isolation, authority RBAC boundaries, and rate limits."""

    async def test_cross_user_document_isolation(self, mock_tourist_auth, mock_tourist_b_auth):
        t1_id, t1_token = mock_tourist_auth
        t2_id, t2_token = mock_tourist_b_auth

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            doc_res = await ac.post(
                "/api/v1/kyc/documents",
                headers={"Authorization": f"Bearer {t1_token}"},
                json={"document_type": "PASSPORT", "masked_identifier": "•••• 1111"},
            )
            doc_id = doc_res.json()["id"]

            # Tourist B attempts to access Tourist A's document
            forbidden_res = await ac.get(
                f"/api/v1/kyc/documents/{doc_id}",
                headers={"Authorization": f"Bearer {t2_token}"},
            )
            assert forbidden_res.status_code == 403

    async def test_tourist_cannot_access_authority_kyc_endpoints(self, mock_tourist_auth):
        _, t_token = mock_tourist_auth
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/api/v1/authority/kyc/pending", headers={"Authorization": f"Bearer {t_token}"})
            assert res.status_code == 403

    async def test_verification_rate_limiting(self):
        client_key = f"rate-limit-test-ip-{uuid.uuid4().hex}"
        # Fill up rate limiter
        for _ in range(60):
            assert credential_service.check_rate_limit(client_key, limit=60, window_seconds=60) is True
        # 61st attempt fails
        assert credential_service.check_rate_limit(client_key, limit=60, window_seconds=60) is False


@pytest.mark.asyncio
class TestConsentAndPrivacyCenter:
    """Test Granular Consents, Withdrawal, and Privacy Center."""

    async def test_consent_lifecycle_and_privacy_center(self, mock_tourist_auth):
        tourist_id, t_token = mock_tourist_auth

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Grant consent
            grant_res = await ac.post(
                "/api/v1/identity/consents",
                headers={"Authorization": f"Bearer {t_token}"},
                json={"consent_type": "LOCATION_PROCESSING", "version": "v1.0"},
            )
            assert grant_res.status_code == 201
            assert grant_res.json()["granted"] is True

            # 2. Check Privacy Center
            privacy_res = await ac.get("/api/v1/identity/privacy", headers={"Authorization": f"Bearer {t_token}"})
            assert privacy_res.status_code == 200
            privacy_data = privacy_res.json()
            assert privacy_data["consents_summary"]["LOCATION_PROCESSING"] is True
            assert "zero trust/risk scoring" in privacy_data["data_minimization_notice"]

            # 3. Withdraw consent with safety explanation
            with_res = await ac.post(
                "/api/v1/identity/consents/LOCATION_PROCESSING/withdraw",
                headers={"Authorization": f"Bearer {t_token}"},
                json={"reason": "Testing opt-out"},
            )
            assert with_res.status_code == 200
            assert with_res.json()["withdrawn"] is True
            assert "geofence" in with_res.json()["safety_impact"]


@pytest.mark.asyncio
class TestProviderAbstractionAndWebhooks:
    """Test KYC provider abstraction, DevKYCProvider disclaimer, and webhook handling."""

    async def test_dev_provider_disclaimer(self):
        provider = provider_registry.get_default_provider()
        assert provider.provider_name == "DEV_KYC_PROVIDER"
        assert provider.is_real_provider is False

    async def test_provider_webhook_signature_and_idempotency(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "event_id": f"evt-{uuid.uuid4().hex}",
                "provider": "DEV_KYC_PROVIDER",
                "event_type": "verification.completed",
                "provider_reference": "DEV-KYC-REF123",
                "status": "COMPLETED",
                "signature": "simulated_sig",
                "data": {},
            }
            # First call
            res1 = await ac.post(
                "/api/v1/kyc/webhooks/DEV_KYC_PROVIDER",
                json=payload,
            )
            assert res1.status_code == 200
            assert res1.json()["status"] == "RECEIVED"

            # Duplicate call (Idempotency)
            res2 = await ac.post(
                "/api/v1/kyc/webhooks/DEV_KYC_PROVIDER",
                json=payload,
            )
            assert res2.status_code == 200
            assert res2.json()["status"] == "ALREADY_PROCESSED"
