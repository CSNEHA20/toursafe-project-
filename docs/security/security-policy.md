# TourSafe Enterprise Information Security Policy

## 1. Principles of Zero Trust
1. **Explicit Verification**: Every incoming request must be independently authenticated and authorized. No internal or external network zone is inherently trusted.
2. **Least Privilege Access**: Users, responders, and administrators receive only the minimal permissions required for their operational scope.
3. **Assume Breach**: Systems, telemetry data, and integration webhooks are inspected and sanitized defensively. All security-relevant actions produce immutable, tamper-evident audit logs.

---

## 2. Authentication & Credential Standards
- **Passwords**: Hashed with Argon2id; minimum 8 characters; rate limited against brute-force guessing.
- **JSON Web Tokens (JWT)**: Signed using HMAC-SHA256 with cryptographically generated secret keys (minimum 32 bytes). Every access token contains standard RFC 7519 claims (`jti`, `iat`, `exp`, `iss`, `aud`).
- **Refresh Token Rotation (RTR)**: Single-use refresh tokens with family tracking. Reusing an old refresh token immediately revokes all tokens within that family.
- **Revocation**: Logout and administrative security actions immediately blacklist token JTIs and session IDs across the application cluster.

---

## 3. Data Protection & Privacy Controls
- **PII Sanitization**: Full phone numbers, email addresses, passwords, and raw coordinates are redacted from application logs (`sanitize_pii_for_logs`).
- **Encryption**: TLS 1.3 enforced for all client-to-backend communication, WebSocket streams, and external provider webhooks.
- **Location Privacy**: Tourist location history is accessible only by the owning tourist profile and authorized command personnel responding to active emergency incidents within their geographic jurisdiction.

---

## 4. Operational Governance & Audit Integrity
- **Separation of Duties**: System administrators, authority supervisors, and field responders have strictly isolated roles (`RBAC`).
- **Cryptographic Hash Chaining**: All administrative decisions, policy updates, and zone modifications are appended to an immutable audit trail chained with SHA-256 integrity hashes.
- **Outbound HTTP Security**: Direct requests to private network ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8, 169.254.169.254) are strictly blocked by the SSRF defense engine.
