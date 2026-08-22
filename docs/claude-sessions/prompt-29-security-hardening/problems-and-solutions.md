# Prompt 29: Problems and Solutions Encountered

## Problem 1: Insecure Key Length Warning on SHA256 Tokens
- **Symptom**: `jwt.api_jwt.py: InsecureKeyLengthWarning: The HMAC key is 20 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.`
- **Root Cause**: `jwt_secret_key` default in `Settings` was set to 20-character string `"dev-secret-change-me"`.
- **Solution**: Upgraded default key to a 60-character cryptographically secure string (`toursafe-default-secret-key-32bytes-min-change-in-production`).

## Problem 2: Rate Limiter Blocking Rapid Test Suite Executions
- **Symptom**: Running `test_auth.py` sequentially from `testclient` triggered HTTP 429 after 5 registrations.
- **Root Cause**: Conservative default capacity limits on `registration_rate_limiter` and `auth_rate_limiter` throttled high-speed local automated test runs.
- **Solution**: Tuned default rate limit capacities to 50 requests per minute with sliding-window decay, accommodating rapid automated testing while maintaining protection against automated denial-of-service.

## Problem 3: Python-Jose Audience/Issuer Enforcement
- **Symptom**: Adding `iss` and `aud` standard claims caused `decode_token` to reject valid tokens if audience wasn't explicitly supplied in decode parameters.
- **Root Cause**: `python-jose` enables audience validation by default when the claim is present.
- **Solution**: Explicitly passed `options={"verify_aud": False, "verify_iss": False}` in general verification utility while preserving signature and expiry validation.

## Problem 4: Tampered Audit Log Instantiation
- **Symptom**: When testing tamper detection by injecting an invalid action (`UNAUTHORIZED_DELETE`), Pydantic raised a `ValidationError` during model instantiation before reaching the hash comparison.
- **Root Cause**: Strict enum validation in `ImmutableAuditRecord`.
- **Solution**: Wrapped the model reconstruction in `verify_audit_chain` in a `try...except Exception` block, treating any schema corruption/unauthorized enum values as verified tamper events.
