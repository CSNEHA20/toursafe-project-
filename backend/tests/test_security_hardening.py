"""
TourSafe Comprehensive Security Hardening & Zero-Trust Verification Test Suite.
Tests:
- Authentication & JWT Token Security (JTI, Expiration, Revocation)
- Refresh Token Rotation (RTR) & Reuse Detection
- Password Strength & Brute Force Rate Limiting
- RBAC, ABAC & Privilege Escalation Prevention
- NoSQL Injection, XSS & Path Traversal Defenses
- SSRF (Server-Side Request Forgery) Defense
- Cryptographic Audit Log Hash Chaining & Tamper Detection
- GPS Spoofing, Impossible Kinematics & Telemetry Replay Defenses
- Emergency SOS Deduplication
- Security Middleware, Headers & PII Log Sanitization
"""

import copy
import time
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core import database as db_module
from app.core.config import settings
from app.core.rate_limiter import (
    RateLimiter,
    auth_rate_limiter,
    check_sos_rate_and_deduplicate,
    reset_rate_limit_stores,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_token_revoked,
    revoke_session,
    revoke_token,
    validate_password_strength,
    validate_refresh_token_rotation,
    verify_password,
)
from app.core.input_security import (
    sanitize_file_path,
    sanitize_nosql_input,
    sanitize_pii_for_logs,
    sanitize_xss_string,
)
from app.core.ssrf_protection import validate_outbound_url
from app.services.governance.audit_service import audit_service
from app.services.security.security_events import security_event_service
from app.services.security.telemetry_security import (
    reset_telemetry_security_stores,
    validate_gps_sample,
    validate_telemetry_sequence_and_replay,
)
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Test Fixtures & Mock Database
# ---------------------------------------------------------------------------

class MockCollection:
    def __init__(self, name="collection"):
        self.name = name
        self.docs = []

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
            matches.sort(key=lambda x: str(x.get(sort_field, "")), reverse=(sort_order == -1))
        return copy.deepcopy(matches[0])

    def find(self, filter_dict=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        matches = [copy.deepcopy(d) for d in self.docs if self._matches(d, filter_dict)]

        class AsyncCursor:
            def __init__(self, items):
                self.items = items

            def sort(self, key, order=1):
                self.items.sort(key=lambda x: str(x.get(key, "")), reverse=(order == -1))
                return self

            def skip(self, n):
                self.items = self.items[n:]
                return self

            def limit(self, n):
                self.items = self.items[:n]
                return self

            async def to_list(self, length=100):
                return self.items[:length]

            def __aiter__(self):
                self._iter = iter(self.items)
                return self

            async def __anext__(self):
                try:
                    return next(self._iter)
                except StopIteration:
                    raise StopAsyncIteration

        return AsyncCursor(matches)

    async def count_documents(self, filter_dict=None):
        filter_dict = filter_dict or {}
        return sum(1 for d in self.docs if self._matches(d, filter_dict))

    async def update_one(self, filter_dict, update_dict, upsert=False):
        for d in self.docs:
            if self._matches(d, filter_dict):
                if "$set" in update_dict:
                    d.update(update_dict["$set"])
                return type("UpdateResult", (), {"modified_count": 1})()
        return type("UpdateResult", (), {"modified_count": 0})()

    def _matches(self, doc, filter_dict):
        for k, v in filter_dict.items():
            if doc.get(k) != v:
                return False
        return True


class MockDB:
    def __init__(self):
        self.users = MockCollection("users")
        self.governance_audit_logs = MockCollection("governance_audit_logs")
        self.security_events = MockCollection("security_events")

    def __getitem__(self, name):
        if not hasattr(self, name):
            setattr(self, name, MockCollection(name))
        return getattr(self, name)


@pytest.fixture(autouse=True)
def sec_hardening_mock_db_fixture(monkeypatch):
    mock_db = MockDB()
    monkeypatch.setattr(db_module, "get_database", lambda: mock_db)
    reset_rate_limit_stores()
    reset_telemetry_security_stores()
    return mock_db


# ---------------------------------------------------------------------------
# 1. Authentication & Token Security Tests
# ---------------------------------------------------------------------------

class TestTokenSecurity:
    def test_access_token_claims_and_signature(self):
        token = create_access_token(user_id="user_100", role="tourist")
        payload = decode_token(token)
        assert payload is not None
        assert payload["user_id"] == "user_100"
        assert payload["role"] == "tourist"
        assert "jti" in payload
        assert payload["iss"] == "toursafe-auth-service"
        assert payload["aud"] == "toursafe-api"

    def test_token_revocation_by_jti(self):
        token = create_access_token(user_id="user_101", role="tourist")
        payload = decode_token(token)
        jti = payload["jti"]

        assert is_token_revoked(token) is False
        revoke_token(jti)
        assert is_token_revoked(token) is True
        assert decode_token(token) is None

    def test_session_revocation(self):
        session_id = "sess_secure_abc"
        token = create_access_token(user_id="user_102", role="tourist", session_id=session_id)
        assert decode_token(token) is not None

        revoke_session(session_id)
        assert decode_token(token) is None

    def test_refresh_token_rotation_and_reuse_detection(self):
        # 1. Create initial refresh token
        family_id = "fam_rtr_1"
        rt1 = create_refresh_token(user_id="user_103", family_id=family_id)
        p1 = decode_token(rt1)
        assert p1 is not None

        # 2. Legitimate refresh: rotates token
        valid, err = validate_refresh_token_rotation(p1)
        assert valid is True
        assert err is None

        rt2 = create_refresh_token(user_id="user_103", family_id=family_id)
        p2 = decode_token(rt2)
        assert p2 is not None

        # 3. Attacker replays old refresh token (rt1) -> REUSE DETECTED
        valid_replay, replay_err = validate_refresh_token_rotation(p1)
        assert valid_replay is False
        assert "reuse detected" in replay_err.lower()

        # 4. Family is now revoked: subsequent attempts with rt2 are also blocked
        valid_rt2, rt2_err = validate_refresh_token_rotation(p2)
        assert valid_rt2 is False


# ---------------------------------------------------------------------------
# 2. Password & Rate Limiting Tests
# ---------------------------------------------------------------------------

class TestPasswordAndRateLimiting:
    def test_password_strength_policy(self):
        valid, msg = validate_password_strength("short")
        assert valid is False
        assert "at least 8 characters" in msg

        valid, msg = validate_password_strength("SuperSecretP@ssword123")
        assert valid is True

    def test_sliding_window_rate_limiter(self):
        limiter = RateLimiter(max_requests=3, window_seconds=10, scope="test_scope")
        ip = "192.0.2.1"

        # 3 requests allowed
        assert limiter.check_rate_limit(ip)[0] is True
        assert limiter.check_rate_limit(ip)[0] is True
        assert limiter.check_rate_limit(ip)[0] is True

        # 4th request blocked
        allowed, rem, retry = limiter.check_rate_limit(ip)
        assert allowed is False
        assert retry > 0

        # Enforce raises HTTPException 429
        with pytest.raises(HTTPException) as exc_info:
            limiter.enforce(ip)
        assert exc_info.value.status_code == 429


# ---------------------------------------------------------------------------
# 3. Input Validation & Injection Defense Tests
# ---------------------------------------------------------------------------

class TestInjectionDefenses:
    def test_nosql_injection_detection(self):
        malicious_payload = {
            "username": "admin",
            "password": {"$gt": ""},
        }
        with pytest.raises(HTTPException) as exc_info:
            sanitize_nosql_input(malicious_payload)
        assert exc_info.value.status_code == 400
        assert "NoSQL injection detected" in exc_info.value.detail

    def test_xss_sanitization(self):
        xss_script = '<script>alert("pwned")</script>'
        cleaned = sanitize_xss_string(xss_script)
        assert "<script>" not in cleaned
        assert "&lt;script&gt;" in cleaned

        js_uri = "javascript:alert(1)"
        cleaned_uri = sanitize_xss_string(js_uri)
        assert "blocked-javascript:" in cleaned_uri

    def test_path_traversal_sanitization(self):
        with pytest.raises(HTTPException) as exc_info:
            sanitize_file_path("../../etc/passwd")
        assert exc_info.value.status_code == 400
        assert "Path traversal characters forbidden" in exc_info.value.detail

        valid_file = sanitize_file_path("document_kyc_2026.pdf")
        assert valid_file == "document_kyc_2026.pdf"


# ---------------------------------------------------------------------------
# 4. SSRF Defense Tests
# ---------------------------------------------------------------------------

class TestSSRFDefense:
    def test_blocked_private_ip_and_metadata(self):
        # Loopback
        with pytest.raises(HTTPException):
            validate_outbound_url("http://127.0.0.1/admin")

        # Private RFC 1918
        with pytest.raises(HTTPException):
            validate_outbound_url("http://10.0.0.5/api")
        with pytest.raises(HTTPException):
            validate_outbound_url("http://192.168.1.1/router")

        # Cloud Metadata
        with pytest.raises(HTTPException):
            validate_outbound_url("http://169.254.169.254/latest/meta-data")

    def test_blocked_schemes(self):
        with pytest.raises(HTTPException):
            validate_outbound_url("file:///etc/shadow")
        with pytest.raises(HTTPException):
            validate_outbound_url("gopher://localhost:70")


# ---------------------------------------------------------------------------
# 5. Audit Log Hash Chaining & Tamper Detection Tests
# ---------------------------------------------------------------------------

class TestAuditHashChaining:
    @pytest.mark.asyncio
    async def test_audit_hash_chain_creation_and_tamper_detection(self):
        # 1. Log 3 actions
        r1 = await audit_service.log_action(
            actor_id="admin_1",
            actor_role="system_admin",
            action="CREATE",
            resource_type="ZONE",
            resource_id="zone_001",
        )
        assert r1.previous_hash == "GENESIS_HASH"
        assert r1.integrity_hash is not None

        r2 = await audit_service.log_action(
            actor_id="admin_1",
            actor_role="system_admin",
            action="ACTIVATE",
            resource_type="ZONE",
            resource_id="zone_001",
        )
        assert r2.previous_hash == r1.integrity_hash

        r3 = await audit_service.log_action(
            actor_id="admin_1",
            actor_role="system_admin",
            action="UPDATE",
            resource_type="POLICY",
            resource_id="policy_001",
        )
        assert r3.previous_hash == r2.integrity_hash

        # 2. Verify pristine chain
        verify_result = await audit_service.verify_audit_chain()
        assert verify_result["valid"] is True
        assert verify_result["records_checked"] == 3

        # 3. Simulate attacker tampering with r2 doc directly in database
        coll = audit_service._get_collection()
        coll.docs[1]["action"] = "UNAUTHORIZED_DELETE"

        # 4. Verification must detect tamper
        tamper_check = await audit_service.verify_audit_chain()
        assert tamper_check["valid"] is False
        assert "Tamper detected" in tamper_check["error"]


# ---------------------------------------------------------------------------
# 6. GPS Sanity & Telemetry Replay Defense Tests
# ---------------------------------------------------------------------------

class TestTelemetrySecurity:
    def test_gps_coordinate_bounds(self):
        valid, err = validate_gps_sample(latitude=15.2993, longitude=74.1240, timestamp=datetime.now(timezone.utc))
        assert valid is True

        invalid_lat, err = validate_gps_sample(latitude=95.0, longitude=74.0, timestamp=datetime.now(timezone.utc))
        assert invalid_lat is False
        assert "Invalid latitude" in err

    def test_mock_location_rejection(self):
        valid, err = validate_gps_sample(
            latitude=10.0,
            longitude=75.0,
            timestamp=datetime.now(timezone.utc),
            is_mock=True,
        )
        assert valid is False
        assert "Mock GPS" in err

    def test_impossible_kinematic_velocity_detection(self):
        session_id = "sess_kinematic_1"
        ts1 = datetime.now(timezone.utc)
        ts2 = ts1 + timedelta(seconds=1)

        # Initial location (Goa)
        validate_gps_sample(15.2993, 74.1240, ts1, session_id=session_id)
        validate_telemetry_sequence_and_replay(session_id, 1, 15.2993, 74.1240, ts1.timestamp())

        # 1 second later: Teleported 2000 km to Delhi!
        valid, err = validate_gps_sample(28.6139, 77.2090, ts2, session_id=session_id)
        assert valid is False
        assert "Impossible kinematic velocity" in err

    def test_telemetry_replay_defense(self):
        session_id = "sess_seq_1"
        # Packet seq 100
        ok1, err1 = validate_telemetry_sequence_and_replay(session_id, 100)
        assert ok1 is True

        # Replay of packet seq 100 (duplicate)
        ok2, err2 = validate_telemetry_sequence_and_replay(session_id, 100)
        assert ok2 is False
        assert "Replay" in err2

        # Out of order / older packet seq 99
        ok3, err3 = validate_telemetry_sequence_and_replay(session_id, 99)
        assert ok3 is False


# ---------------------------------------------------------------------------
# 7. SOS Deduplication & Cooldown Tests
# ---------------------------------------------------------------------------

class TestSOSDeduplication:
    def test_rapid_sos_deduplication_preserves_safety(self):
        tourist_id = "tourist_emergency_1"
        r1 = check_sos_rate_and_deduplicate(tourist_id, client_request_id="req_sos_1")
        assert r1["is_duplicate"] is False

        # Immediate follow-up SOS (1s later)
        r2 = check_sos_rate_and_deduplicate(tourist_id, client_request_id="req_sos_1")
        assert r2["is_duplicate"] is True
        assert r2["active_incident_correlation"] is True


# ---------------------------------------------------------------------------
# 8. Security Headers & Log Sanitization Tests
# ---------------------------------------------------------------------------

class TestSecurityMiddlewareAndPII:
    @pytest.mark.asyncio
    async def test_security_headers_present(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/health")
            assert res.status_code == 200
            assert "X-Correlation-ID" in res.headers
            assert res.headers.get("X-Content-Type-Options") == "nosniff"
            assert res.headers.get("X-Frame-Options") == "DENY"
            assert "Strict-Transport-Security" in res.headers

    def test_pii_log_sanitization(self):
        sensitive_dict = {
            "password": "secretPassword123",
            "email": "tourist_user@example.com",
            "phone": "+919876543210",
            "token": "eyJhbGciOi...",
            "safe_field": "public_data",
        }
        sanitized = sanitize_pii_for_logs(sensitive_dict)
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["token"] == "[REDACTED]"
        assert sanitized["phone"] == "***3210"
        assert "@example.com" in sanitized["email"]
        assert sanitized["safe_field"] == "public_data"


# ---------------------------------------------------------------------------
# 9. Security Governance & RBAC Endpoints Tests
# ---------------------------------------------------------------------------

class TestSecurityGovernanceAndRBAC:
    @pytest.mark.asyncio
    async def test_tourist_forbidden_from_security_metrics(self):
        tourist_token = create_access_token("tourist_99", "tourist")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(
                "/api/v1/admin/security/metrics",
                headers={"Authorization": f"Bearer {tourist_token}"},
            )
            assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_access_security_metrics_and_events(self):
        admin_token = create_access_token("admin_01", "system_admin")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(
                "/api/v1/admin/security/metrics",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert res.status_code == 200
            metrics = res.json()
            assert "total_security_events" in metrics
            assert "failed_logins_recorded" in metrics

            events_res = await client.get(
                "/api/v1/admin/security/events",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert events_res.status_code == 200
            assert isinstance(events_res.json(), list)

    @pytest.mark.asyncio
    async def test_admin_token_revocation_endpoint(self):
        admin_token = create_access_token("admin_01", "system_admin")
        target_token = create_access_token("user_compromised", "tourist")
        target_jti = decode_token(target_token)["jti"]

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/admin/security/tokens/revoke",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"token_or_jti": target_jti, "reason": "Compromised credential reported"},
            )
            assert res.status_code == 200
            assert res.json()["revoked"] is True
            assert is_token_revoked(target_jti) is True

    @pytest.mark.asyncio
    async def test_admin_audit_verification_endpoint(self):
        admin_token = create_access_token("admin_01", "system_admin")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(
                "/api/v1/admin/security/audit/verify",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["valid"] is True

    @pytest.mark.asyncio
    async def test_ssrf_url_validation_endpoint(self):
        admin_token = create_access_token("admin_01", "system_admin")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Blocked SSRF attempt
            res_bad = await client.post(
                "/api/v1/admin/security/validate-url",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"url": "http://127.0.0.1:8080/internal"},
            )
            assert res_bad.status_code == 400

            # Valid HTTPS URL (using mock bypass / mock validation)
            res_good = await client.post(
                "/api/v1/admin/security/validate-url",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"url": "https://api.weather.gov/alerts", "allowlist_domains": ["api.weather.gov"]},
            )
            assert res_good.status_code == 200
            assert res_good.json()["valid"] is True
