# Problems and Solutions — Prompt 13

## 1. Async Redis Client Unawaited Warning
- **Problem**: `get_redis_client()` is an asynchronous function returning the Redis pool, but initial calls in location service lacked `await`.
- **Solution**: Updated all invocations to `await get_redis_client()` with graceful in-memory fallback if Redis is unreachable.

## 2. Notification Service Signature Mismatch
- **Problem**: `send_notification` was called with keyword arguments not matching the exact method signature.
- **Solution**: Aligned caller arguments in `assignment_service.py` to `(recipient, channel, subject, message, incident_id, recipient_type, metadata)`.

## 3. Mock Database Missing Extended Collections in Legacy Test
- **Problem**: When running the full suite, `test_emergency_response.py` failed because `MockDatabase` lacked `responder_units` attribute.
- **Solution**: Added `__getattr__` and explicit collection initializations to `MockDatabase` across test files.

## 4. Responder Interface TypeScript Property Misalignment
- **Problem**: `npx tsc` failed due to missing properties on `Responder` interface (`tracking_active`, `current_location.accuracy`, `ON_SCENE` status).
- **Solution**: Updated `interface Responder` in `frontend/types/index.ts` with complete typed fields.
