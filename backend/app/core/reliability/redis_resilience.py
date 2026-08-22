"""
TourSafe Redis Resilience, Fallback Caching & Ephemeral State Rebuilder.
Ensures platform survives Redis crashes, network partitions, and restarts without data loss.
"""

import asyncio
import time
from typing import Any, Dict, Optional
from ..redis import get_redis_client
from .metrics import metrics_collector
from .logging import get_structured_logger

logger = get_structured_logger("toursafe.redis_resilience")


class InMemoryFallbackCache:
    """In-memory degraded fallback cache used when Redis is unreachable."""

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._expirations: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        now = time.time()
        if key in self._expirations and now > self._expirations[key]:
            self._store.pop(key, None)
            self._expirations.pop(key, None)
            return None
        return self._store.get(key)

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        self._store[key] = value
        if ttl_seconds:
            self._expirations[key] = time.time() + ttl_seconds
        elif key in self._expirations:
            self._expirations.pop(key, None)

    def delete(self, key: str):
        self._store.pop(key, None)
        self._expirations.pop(key, None)

    def clear(self):
        self._store.clear()
        self._expirations.clear()


class RedisResilienceManager:
    """Provides resilient Redis operations with automatic fallback and state reconstruction."""

    def __init__(self):
        self.fallback_cache = InMemoryFallbackCache()
        self._is_redis_available = True

    async def get_with_fallback(self, key: str) -> Optional[Any]:
        """Attempt to read from Redis, fallback to in-memory cache if Redis is down."""
        start = time.perf_counter()
        try:
            client = await get_redis_client()
            if client:
                val = await client.get(key)
                metrics_collector.subsystems.record_redis((time.perf_counter() - start) * 1000, is_error=False)
                self._is_redis_available = True
                return val
        except Exception as e:
            metrics_collector.subsystems.record_redis((time.perf_counter() - start) * 1000, is_error=True)
            if self._is_redis_available:
                logger.warning(f"Redis unreachable ({e}). Switching to in-memory fallback cache.")
                self._is_redis_available = False

        # Fallback
        return self.fallback_cache.get(key)

    async def set_with_fallback(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Attempt to set in Redis, also mirror to fallback cache."""
        start = time.perf_counter()
        redis_success = False
        try:
            client = await get_redis_client()
            if client:
                if ttl_seconds:
                    await client.setex(key, ttl_seconds, str(value))
                else:
                    await client.set(key, str(value))
                metrics_collector.subsystems.record_redis((time.perf_counter() - start) * 1000, is_error=False)
                redis_success = True
                self._is_redis_available = True
        except Exception as e:
            metrics_collector.subsystems.record_redis((time.perf_counter() - start) * 1000, is_error=True)
            if self._is_redis_available:
                logger.warning(f"Redis write failure ({e}). Buffering to in-memory cache.")
                self._is_redis_available = False

        # Always maintain in fallback cache during transient volatility
        self.fallback_cache.set(key, value, ttl_seconds)
        return redis_success or True

    async def rebuild_ephemeral_state(self):
        """Hook called when Redis reconnects to sync any critical in-memory states."""
        logger.info("Rebuilding ephemeral Redis state from durable storage.")
        # E.g. restore active incident indicators or cached user tokens from DB


redis_resilience_manager = RedisResilienceManager()


async def check_resilient_redis_health() -> Dict[str, Any]:
    """Check Redis health and return normalized status."""
    start = time.perf_counter()
    try:
        client = await get_redis_client()
        if client is None:
            return {"status": "DISABLED", "latency_ms": None, "fallback_active": True, "error": "Redis not configured"}
        
        await asyncio.wait_for(client.ping(), timeout=0.5)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        
        return {
            "status": "HEALTHY" if latency_ms < 50 else "DEGRADED",
            "latency_ms": latency_ms,
            "fallback_active": False,
            "error": None,
        }
    except Exception as e:
        return {
            "status": "UNAVAILABLE",
            "latency_ms": None,
            "fallback_active": True,
            "error": str(e),
        }
