# Prompt 4 Problems & Solutions: Real-Time Communication Infrastructure

## Problem 1: Health Check and Startup Pings Hanging on Offline Dependencies
- **Cause**: When running health checks or starting up without a live MongoDB or Redis instance, default client connection timeouts (e.g. PyMongo/Motor 30-second serverSelectionTimeoutMS) caused the health check endpoint and test runner to hang.
- **Solution**: Wrapped the MongoDB `ping` command and Redis `client.ping()` in `asyncio.wait_for(..., timeout=0.5)`.
- **Verification**: Health endpoint now responds in milliseconds and reports `degraded` or `unavailable` status cleanly without blocking.

---

## Problem 2: Starlette TestClient Synchronous Deadlock on Multi-Step WebSocket Calls
- **Cause**: Synchronous TestClient with WebSocket connection could block when attempting simultaneous HTTP requests across the same thread.
- **Solution**: Refactored the test suite to execute HTTP dev test event publisher and WebSocket assertions in dedicated cleanly-scoped test cases, verifying both the REST endpoint and the event bus broadcast mechanics independently.
- **Verification**: All 20 tests in `test_realtime.py` pass within 1.3 seconds.

---

## Problem 3: Pydantic v2 Deprecation Warnings on Field Annotations and Custom Validators
- **Cause**: Usage of Pydantic v1 style `@validator` and `Field(..., example="...")` in settings and realtime schemas triggered deprecation warnings.
- **Solution**: Migrated to Pydantic v2 `@field_validator` with `mode="before"` and `Field(..., json_schema_extra={"example": "..."})`.
- **Verification**: Pydantic schema validation executes cleanly without schema deprecation warnings.
