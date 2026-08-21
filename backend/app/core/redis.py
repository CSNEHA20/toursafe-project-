import asyncio
import logging
from typing import Optional
import redis.asyncio as aioredis
from .config import settings

logger = logging.getLogger("toursafe.redis")

_redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> Optional[aioredis.Redis]:
    """
    Get or initialize the asynchronous Redis connection pool.
    Returns None if Redis cannot be reached, allowing graceful degradation.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    if not settings.redis_url:
        return None

    try:
        client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        # Test ping with timeout
        await asyncio.wait_for(client.ping(), timeout=0.5)
        _redis_client = client
        logger.info("Connected to Redis at %s", settings.redis_url)
        return _redis_client
    except Exception as e:
        logger.warning("Redis not reachable (%s). Operating in degraded in-memory mode.", e)
        _redis_client = None
        return None


async def close_redis():
    """Close the active Redis connection pool."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.warning("Error closing Redis: %s", e)
        finally:
            _redis_client = None


async def check_redis_health() -> dict:
    """
    Check the health and latency of the Redis service.
    Returns a status dict suitable for health endpoints.
    """
    if not settings.redis_url:
        return {
            "status": "disabled",
            "message": "Redis URL is not configured",
        }

    try:
        import time
        client = aioredis.from_url(
            settings.redis_url,
            socket_connect_timeout=0.3,
            socket_timeout=0.3,
        )
        start = time.perf_counter()
        await asyncio.wait_for(client.ping(), timeout=0.3)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        await client.close()
        return {
            "status": "healthy",
            "latency_ms": latency_ms,
            "url": settings.redis_url.split("@")[-1],  # redact credentials if any
        }
    except Exception as e:
        return {
            "status": "unavailable",
            "error": str(e),
            "message": "Redis server unavailable; system operating in standalone memory mode",
        }

