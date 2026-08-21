# Prompt 5: Problems and Solutions

## Problem 1: MongoDB Standalone Connection in Offline Test Environment
- **Problem**: Running pytest directly attempted to connect to `localhost:27017` which timed out when running in environments without a local MongoDB service running.
- **Cause**: Tests executed HTTP requests against endpoints that performed database operations directly.
- **Solution**: Implemented `MockAppDatabase` with full support for filtering, projection, cursor pagination, and async iterator (`__aiter__` / `__anext__`), monkeypatching `get_database` in test fixtures.
- **Verification**: `python -m pytest tests/test_location.py` executes in under 2 seconds with 100% pass rate.

## Problem 2: Parameter Signature for JWT Token Creation in Tests
- **Problem**: `create_access_token` fixture in test file threw `TypeError: missing 1 required positional argument: 'role'`.
- **Cause**: The test fixture initially passed a single dictionary payload rather than positional `(user_id, role)`.
- **Solution**: Updated fixtures to call `create_access_token("tourist_user_1", "tourist")` and `create_access_token("auth_user_1", "authority")`.
- **Verification**: All 20 tests in `test_location.py` passed immediately.
