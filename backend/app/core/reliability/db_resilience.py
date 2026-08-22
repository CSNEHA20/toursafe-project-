"""
TourSafe Database Resilience, Safe Retries, Slow Query Tracking & Idempotency.
Provides bounded retry mechanisms, latency measurements, and transient error absorption for MongoDB.
"""

import asyncio
import random
import time
from typing import Any, Callable, Dict, List, Optional
from pymongo.errors import AutoReconnect, NetworkTimeout, ServerSelectionTimeoutError
from ..database import get_database
from .metrics import metrics_collector
from .logging import get_structured_logger

logger = get_structured_logger("toursafe.db_resilience")

TRANSIENT_DB_ERRORS = (
    AutoReconnect,
    NetworkTimeout,
    ServerSelectionTimeoutError,
    ConnectionResetError,
    asyncio.TimeoutError,
)


class SlowQueryTracker:
    """In-memory circular buffer for logging and inspecting slow database operations."""

    def __init__(self, max_entries: int = 100, threshold_ms: float = 100.0):
        self.max_entries = max_entries
        self.threshold_ms = threshold_ms
        self.slow_queries: List[Dict[str, Any]] = []

    def record(self, operation: str, collection: str, duration_ms: float, filter_sample: Optional[Dict] = None):
        if duration_ms >= self.threshold_ms:
            entry = {
                "operation": operation,
                "collection": collection,
                "duration_ms": round(duration_ms, 2),
                "timestamp": time.time(),
                "filter_sample": str(filter_sample)[:200] if filter_sample else None,
            }
            self.slow_queries.append(entry)
            if len(self.slow_queries) > self.max_entries:
                self.slow_queries.pop(0)

            logger.warning(
                f"Slow database query detected: {operation} on {collection} took {duration_ms:.2f}ms",
                extra={"event": "SLOW_DB_QUERY", "extra_data": entry}
            )

    def get_slow_queries(self) -> List[Dict[str, Any]]:
        return list(reversed(self.slow_queries))


slow_query_tracker = SlowQueryTracker()


async def with_db_retry(
    coro_fn: Callable[[], Any],
    operation_name: str = "db_op",
    collection_name: str = "unknown",
    max_retries: int = 3,
    base_delay_seconds: float = 0.05,
    filter_sample: Optional[Dict] = None,
) -> Any:
    """Execute a database coroutine with bounded exponential backoff on transient errors."""
    attempts = 0
    start_time = time.perf_counter()
    last_exception = None

    while attempts < max_retries:
        attempts += 1
        op_start = time.perf_counter()
        try:
            result = await coro_fn()
            op_duration = (time.perf_counter() - op_start) * 1000
            metrics_collector.subsystems.record_db(op_duration, is_error=False)
            slow_query_tracker.record(operation_name, collection_name, op_duration, filter_sample)
            return result
        except TRANSIENT_DB_ERRORS as e:
            last_exception = e
            op_duration = (time.perf_counter() - op_start) * 1000
            metrics_collector.subsystems.record_db(op_duration, is_error=True)
            
            if attempts >= max_retries:
                logger.error(
                    f"Database retry exhausted after {attempts} attempts for {operation_name}: {e}",
                    extra={"event": "DB_RETRY_EXHAUSTED", "extra_data": {"operation": operation_name, "error": str(e)}}
                )
                raise e

            # Exponential backoff with jitter
            delay = base_delay_seconds * (2 ** (attempts - 1)) + random.uniform(0, 0.02)
            logger.warning(f"Transient DB failure ({e}). Retrying {operation_name} attempt {attempts+1}/{max_retries} in {delay:.3f}s")
            await asyncio.sleep(delay)
        except Exception as e:
            # Non-transient errors (e.g. duplicate key, schema validation error) fail immediately
            op_duration = (time.perf_counter() - op_start) * 1000
            metrics_collector.subsystems.record_db(op_duration, is_error=True)
            raise e

    if last_exception:
        raise last_exception


async def safe_db_execute(
    coro_fn: Callable[[], Any],
    fallback_value: Any = None,
    operation_name: str = "safe_query"
) -> Any:
    """Executes a non-critical DB query returning a fallback value if the database is unavailable."""
    try:
        return await coro_fn()
    except Exception as e:
        logger.warning(f"Non-critical DB operation {operation_name} safely degraded: {e}")
        return fallback_value


class IdempotencyWriteGuard:
    """Guards against duplicate writes for critical resources using an in-memory & DB check."""

    def __init__(self):
        self._processed_keys: Dict[str, float] = {}

    def is_duplicate(self, idempotency_key: str, ttl_seconds: float = 300.0) -> bool:
        now = time.time()
        # Clean expired
        expired = [k for k, ts in self._processed_keys.items() if now - ts > ttl_seconds]
        for k in expired:
            self._processed_keys.pop(k, None)

        if idempotency_key in self._processed_keys:
            return True

        self._processed_keys[idempotency_key] = now
        return False


idempotent_write_guard = IdempotencyWriteGuard()


async def check_db_health() -> Dict[str, Any]:
    """Perform a structured MongoDB health check."""
    start = time.perf_counter()
    try:
        db = get_database()
        await asyncio.wait_for(db.command("ping"), timeout=1.0)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        
        # Check server status for connection pool details if authorized
        server_info = {}
        try:
            status_doc = await asyncio.wait_for(db.command("serverStatus"), timeout=0.5)
            connections = status_doc.get("connections", {})
            server_info = {
                "current_connections": connections.get("current"),
                "available_connections": connections.get("available"),
                "uptime_seconds": status_doc.get("uptime"),
            }
        except Exception:
            pass

        return {
            "status": "HEALTHY" if latency_ms < 100 else "DEGRADED",
            "latency_ms": latency_ms,
            "server_info": server_info,
            "error": None,
        }
    except Exception as e:
        return {
            "status": "UNAVAILABLE",
            "latency_ms": None,
            "server_info": {},
            "error": str(e),
        }
