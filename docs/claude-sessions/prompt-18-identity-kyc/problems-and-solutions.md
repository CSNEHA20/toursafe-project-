# Problems and Solutions: Prompt 18 — Identity, KYC & Digital Tourist Credential

## Problem 1: Direct Module Import Binding in Fast Unit Tests
- **Problem**: When pytest executed test cases with monkeypatched databases, services that imported `from ...core.database import get_database` held direct function references to the unpatched database connector, causing tests to wait for live MongoDB connections.
- **Cause**: Python `from module import function` binds the function symbol at import time.
- **Solution**: Updated identity services and routers to access database functions dynamically (`from ...core import database as db_core; def get_database(): return db_core.get_database()`), allowing test fixtures to transparently swap `mock_db`.
- **Verification**: Tests run in under 4 seconds completely in-memory with 100% pass rate.

---

## Problem 2: Handling Issuance Gate on Profiles Without Prior Metadata
- **Problem**: Calling `/api/v1/credentials/issue/{tourist_id}` for a newly registered user who hadn't started KYC failed with a 404 (Identity profile not found) instead of a 400 (KYC status is NOT_STARTED, must be VERIFIED).
- **Cause**: `issue_credential` attempted a raw `find_one` on the identity profile table before bootstrapping a default profile.
- **Solution**: Updated `issue_credential` to call `await kyc_service.get_or_create_identity_profile(user_id)`. If the profile status is not `VERIFIED`, it raises `PermissionError("Cannot issue digital credential. KYC status is 'NOT_STARTED', must be 'VERIFIED'")`, which correctly maps to 400 Bad Request.
- **Verification**: `test_cannot_issue_credential_if_not_verified` passed with status 400.

---

## Problem 3: Preventing QR Code Replay Attacks
- **Problem**: If a tourist takes a screenshot of their valid QR code and shares it, or an expired credential is cloned, how can the authority verifier detect token freshness and allow user revocation?
- **Cause**: Static QR payloads without cryptographic nonces or status lookups are vulnerable to replay attacks.
- **Solution**:
  1. Implemented on-demand QR token nonce rotation (`POST /api/v1/credentials/me/rotate-qr`).
  2. Public/Authority verification endpoint always queries active database status and checks revocation/suspension flags before returning `VALID`.
- **Verification**: `test_credential_suspension_and_revocation` and `test_qr_token_rotation` pass.
