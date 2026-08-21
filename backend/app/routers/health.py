import asyncio
import logging
import time
from fastapi import APIRouter
from ..core.connection_manager import connection_manager
from ..core.database import get_database
from ..core.redis import check_redis_health

logger = logging.getLogger("toursafe.health")

router = APIRouter(tags=["Health"])


@router.get("/health")
@router.get("/api/v1/health")
async def health_check():
    """
    Comprehensive multi-service health check endpoint.
    Reports backend, MongoDB, Redis, and Realtime WebSocket layer status.
    """
    # 1. MongoDB check with timeout
    mongo_status = "unavailable"
    mongo_latency_ms = None
    mongo_error = None
    try:
        db = get_database()
        start = time.perf_counter()
        await asyncio.wait_for(db.command("ping"), timeout=0.5)
        mongo_latency_ms = round((time.perf_counter() - start) * 1000, 2)
        mongo_status = "healthy"
    except Exception as e:
        mongo_error = str(e)

    # 2. Redis check
    redis_info = await check_redis_health()

    # 3. Realtime connection manager check
    realtime_stats = connection_manager.get_stats()
    realtime_status = {
        "status": "healthy",
        "transport": "websocket",
        "active_connections": realtime_stats["active_connections"],
        "unique_users": realtime_stats["unique_users"],
        "active_channels": realtime_stats["active_channels"],
    }

    # Determine overall status
    if mongo_status == "healthy":
        if redis_info.get("status") in ["healthy", "disabled"]:
            overall_status = "healthy"
        else:
            overall_status = "degraded"  # Auxiliary Redis cache offline, core operational
    else:
        overall_status = "unavailable"

    return {
        "status": overall_status,
        "services": {
            "backend": {"status": "healthy", "version": "1.0.0"},
            "mongodb": {
                "status": mongo_status,
                "latency_ms": mongo_latency_ms,
                "error": mongo_error,
            },
            "redis": redis_info,
            "realtime": realtime_status,
        },
    }

