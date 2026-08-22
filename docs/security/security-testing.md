# TourSafe Security Testing Guide & Penetration Test Scenarios

## 1. Automated Security Test Suite
The security test suite (`backend/tests/test_security_hardening.py`) executes 24 automated penetration-style tests:

```bash
# Execute security hardening test suite
cd backend
python -m pytest tests/test_security_hardening.py -v
```

### Verified Test Categories:
1. **Authentication & Token Lifecycle**:
   - `test_access_token_claims_and_signature`: Verifies RFC 7519 claims (`jti`, `iat`, `exp`, `iss`, `aud`).
   - `test_token_revocation_by_jti`: Verifies token blacklisting and immediate rejection.
   - `test_session_revocation`: Verifies multi-token session invalidation.
   - `test_refresh_token_rotation_and_reuse_detection`: Simulates token theft/replay, verifying family invalidation.
2. **Password & Rate Limiting**:
   - `test_password_strength_policy`: Enforces minimum 8 character reasonable complexity.
   - `test_sliding_window_rate_limiter`: Verifies sliding-window request throttling and HTTP 429 Retry-After response.
3. **Input Security & Injection Defense**:
   - `test_nosql_injection_detection`: Tests deep operator injection (`$gt`, `$ne`, `$where`) in JSON bodies.
   - `test_xss_sanitization`: Tests script tag stripping and `javascript:` URI neutralization.
   - `test_path_traversal_sanitization`: Tests directory traversal sequences (`../`, `..\\`).
4. **SSRF Defense**:
   - `test_blocked_private_ip_and_metadata`: Tests blocked loopback (127.0.0.1), private RFC 1918 (10.0.0.0/8), and cloud metadata (169.254.169.254).
   - `test_blocked_schemes`: Tests blocked non-HTTP protocols (`file://`, `gopher://`).
5. **Audit Hash Chaining & Tamper Detection**:
   - `test_audit_hash_chain_creation_and_tamper_detection`: Verifies SHA-256 hash chaining and detects manual database alterations.
6. **Kinematic GPS Sanity & Telemetry Replay**:
   - `test_gps_coordinate_bounds`: Tests boundary limits for lat/lon coordinates.
   - `test_mock_location_rejection`: Tests mock GPS flag rejection.
   - `test_impossible_kinematic_velocity_detection`: Tests supersonic teleportation detection (>350 m/s).
   - `test_telemetry_replay_defense`: Tests duplicate sequence number and stale packet rejection.
7. **Emergency SOS Deduplication**:
   - `test_rapid_sos_deduplication_preserves_safety`: Verifies safety-critical SOS deduplication without failing dispatch.
8. **Security Middleware & Logging**:
   - `test_security_headers_present`: Verifies HSTS, CSP, X-Frame-Options, X-Content-Type-Options, and X-Correlation-ID.
   - `test_pii_log_sanitization`: Verifies PII redaction of tokens, passwords, and phone numbers.
9. **RBAC & Security Governance Endpoints**:
   - `test_tourist_forbidden_from_security_metrics`: Tests 403 access control.
   - `test_admin_can_access_security_metrics_and_events`: Verifies admin security posture visibility.
   - `test_admin_token_revocation_endpoint`: Verifies administrative token revocation endpoint.
   - `test_admin_audit_verification_endpoint`: Verifies cryptographic hash chain verification API.
   - `test_ssrf_url_validation_endpoint`: Verifies URL compliance testing API.
