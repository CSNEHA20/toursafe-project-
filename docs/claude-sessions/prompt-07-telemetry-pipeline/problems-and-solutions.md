# Prompt 7: Problems and Solutions

## Problem 1: Redis Timeout Penalties During High-Frequency Stream Testing
- **Symptoms**: Pytest execution hung for 15-20 seconds on simulated 50 Hz streaming when Redis was not running locally.
- **Root Cause**: `redis.asyncio` default connection socket timeout waited 500ms per attempt on failed reconnects.
- **Solution**: Added a reconnect cooldown mechanism (`_last_redis_fail_time` with 5s threshold) in `app.core.redis` and monkeypatched Redis cleanly during unit test execution.

## Problem 2: Async Worker Background Loop Hanging Test Teardown
- **Symptoms**: Async tests hung indefinitely at completion waiting for background asyncio tasks to terminate.
- **Root Cause**: `TelemetryIngestionQueue._worker_loop` was running an infinite `while True: await queue.get()`.
- **Solution**: Refactored the worker to a drain-based pattern (`while not self._queue.empty(): ...`) that naturally terminates and frees its task handle once the queue is processed, plus added `shutdown_sync()` on test fixtures.

## Problem 3: Module-Bound `get_database()` Reference During Monkeypatching
- **Symptoms**: `AttributeError: <module> has no attribute 'get_database'` or monkeypatch failed to replace motor database client in modules that used `from ...core.database import get_database`.
- **Root Cause**: Direct import binding prevented runtime replacement of the database reference across modules.
- **Solution**: Standardized imports across `main.py`, `telemetry.py`, `session.py`, and `persistence.py` to `from ..core import database as db_core` and calling `db_core.get_database()`.
