# Prompt 29: Architectural & Design Decisions

## 1. Refresh Token Rotation (RTR) with Family Invalidation
- **Decision**: Implemented single-use refresh tokens linked to a `family_id`. When a refresh token is exchanged, a new access token and new refresh token are generated, and the old token is invalidated. If an already-consumed refresh token is re-presented, the system flags a `CRITICAL` token reuse event and immediately revokes all tokens within that family.
- **Rationale**: Mitigates refresh token theft and replay attacks without requiring immediate re-login for legitimate users.

## 2. Safety-Critical SOS Deduplication Without Blocking
- **Decision**: Unlike standard rate limiting that returns HTTP 429 and drops requests, emergency SOS submissions within the cooldown window (5 seconds) are deduplicated and correlated with the existing active emergency incident.
- **Rationale**: A panicked tourist rapidly tapping the SOS button must NEVER be locked out of emergency dispatch.

## 3. Cryptographic Hash Chaining for Audit Logs
- **Decision**: Chained every `ImmutableAuditRecord` to its predecessor's `integrity_hash` using `previous_hash`.
- **Rationale**: Provides verifiable non-repudiation and automated tamper detection (`verify_audit_chain`) against internal and external unauthorized database modifications.

## 4. Defense-in-Depth SSRF Validation
- **Decision**: Built a multi-stage outbound URL validator verifying protocol schemes (`http`, `https`), resolving DNS, and strictly blocking loopback, private RFC 1918 subnets, and cloud metadata IPs (`169.254.169.254`).
- **Rationale**: Prevents external integrations from being leveraged as proxies into internal cloud resources.
