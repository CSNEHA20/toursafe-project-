"""
TourSafe Analytics Caching Layer

Provides Redis-backed caching for computationally intensive analytical aggregates,
with structured key namespacing, tenant/role isolation, dynamic TTL computation,
and graceful fallback to memory/direct computation.
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple
from ...core.redis import get_redis_client

logger = logging.getLogger("toursafe.analytics.cache")

# Default TTL configuration (seconds)
TTL_REALTIME_SECONDS = 30       # Realtime operational snapshots
TTL_HOURLY_SECONDS = 120        # Today's hourly buckets
TTL_DAILY_SECONDS = 600         # Multi-day aggregate buckets
TTL_HISTORICAL_SECONDS = 3600   # Immutable past ranges (> 7 days old)

_memory_cache: Dict[str, Tuple[str, float]] = {}  # key -> (json_str, expire_timestamp)


class AnalyticsCache:
    """
    Manages caching for analytical aggregation pipelines.
    """

    def generate_cache_key(
        self,
        tenant_id: str,
        metric: str,
        params: Dict[str, Any],
        version: str = "v1",
    ) -> str:
        """
        Creates a deterministic Redis key incorporating tenant isolation, metric name,
        and sorted parameter payload hash.
        """
        cleaned_params = {k: v for k, v in sorted(params.items()) if v is not None and k != "bypass_cache"}
        params_str = json.dumps(cleaned_params, sort_keys=True, default=str)
        param_hash = hashlib.sha256(params_str.encode("utf-8")).hexdigest()[:16]
        return f"toursafe:analytics:{tenant_id}:{metric}:{version}:{param_hash}"

    def calculate_ttl(self, start_time: Optional[str], end_time: Optional[str], granularity: str) -> int:
        """
        Calculates dynamic TTL. Older historical windows get longer TTLs since historical data is mostly immutable.
        """
        if not end_time:
            return TTL_REALTIME_SECONDS

        try:
            from datetime import datetime, timezone
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age_hours = (now - end_dt).total_seconds() / 3600.0

            if age_hours > 48.0:
                return TTL_HISTORICAL_SECONDS
            elif age_hours > 24.0:
                return TTL_DAILY_SECONDS
            elif granularity == "hour":
                return TTL_HOURLY_SECONDS
            else:
                return TTL_DAILY_SECONDS
        except Exception:
            return TTL_DAILY_SECONDS

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves cached JSON document from Redis or memory fallback.
        """
        try:
            redis = await get_redis_client()
            if redis is not None:
                val = await redis.get(key)
                if val:
                    data = json.loads(val)
                    if isinstance(data, dict):
                        data["_cached"] = True
                    return data
        except Exception as e:
            logger.debug("Redis cache get error (%s). Checking memory cache.", e)

        # Fallback to memory cache
        if key in _memory_cache:
            raw_str, expire_at = _memory_cache[key]
            if time.time() < expire_at:
                try:
                    data = json.loads(raw_str)
                    if isinstance(data, dict):
                        data["_cached"] = True
                    return data
                except Exception:
                    pass
            else:
                _memory_cache.pop(key, None)

        return None

    async def set(self, key: str, data: Dict[str, Any], ttl_seconds: int = TTL_DAILY_SECONDS) -> bool:
        """
        Persists JSON-serializable analytical payload to Redis and memory fallback.
        """
        try:
            payload_str = json.dumps(data, default=str)
            redis = await get_redis_client()
            if redis is not None:
                await redis.set(key, payload_str, ex=ttl_seconds)
                return True
        except Exception as e:
            logger.debug("Redis cache set error (%s). Storing in memory fallback.", e)

        # Memory cache fallback
        try:
            payload_str = json.dumps(data, default=str)
            _memory_cache[key] = (payload_str, time.time() + ttl_seconds)
            # Prune memory cache if oversized
            if len(_memory_cache) > 2000:
                now = time.time()
                expired = [k for k, v in _memory_cache.items() if v[1] < now]
                for k in expired:
                    _memory_cache.pop(k, None)
            return True
        except Exception as e:
            logger.error("Failed to store analytics in memory cache: %s", e)
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidates keys matching a given pattern across Redis and memory cache.
        """
        count = 0
        try:
            redis = await get_redis_client()
            if redis is not None:
                keys = await redis.keys(pattern)
                if keys:
                    count = await redis.delete(*keys)
        except Exception as e:
            logger.debug("Redis cache invalidation error: %s", e)

        # Invalidate memory cache
        import fnmatch
        to_del = [k for k in _memory_cache.keys() if fnmatch.fnmatch(k, pattern)]
        for k in to_del:
            _memory_cache.pop(k, None)
            count += 1

        return count


analytics_cache = AnalyticsCache()
