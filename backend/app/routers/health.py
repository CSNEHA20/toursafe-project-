"""
TourSafe Comprehensive Health Check, Liveness, Readiness & Startup Router.
"""

import asyncio
import time
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Response
from ..core.connection_manager import connection_manager
from ..core.database import get_database
from ..core.reliability.db_resilience import check_db_health
from ..core.reliability.redis_resilience import check_resilient_redis_health
from ..core.reliability.degradation import degradation_manager, SystemMode
from ..core.reliability.metrics import metrics_collector
from .auth import get_current_user
from ..core.config import settings
from ..core.reliability.logging import get_structured_logger

logger = get_structured_logger("toursafe.health")

router = APIRouter(tags=["Health & Probes"])


@router.get("/health/live")
async def liveness_check():
    """
    Liveness probe: answers 'Is this process alive?'.
    Intentionally lightweight, non-cascading, zero downstream DB dependencies.
    """
    return {
        "status": "HEALTHY",
        "timestamp": time.time(),
        "uptime_seconds": metrics_collector.get_uptime_seconds(),
    }


@router.get("/health/ready")
async def readiness_check():
    """
    Readiness probe: answers 'Can this instance safely receive user traffic?'.
    Checks critical dependencies (MongoDB).
    """
    mongo_health = await check_db_health()
    redis_health = await check_resilient_redis_health()

    is_ready = mongo_health["status"] in ["HEALTHY", "DEGRADED"]
    current_mode = degradation_manager.current_mode

    status_str = "HEALTHY" if (is_ready and current_mode != SystemMode.OFFLINE) else "UNAVAILABLE"

    return {
        "status": status_str,
        "mode": current_mode.value,
        "dependencies": {
            "mongodb": mongo_health["status"],
            "redis": redis_health["status"],
        },
        "ready": is_ready,
    }


@router.get("/health/startup")
async def startup_check():
    """
    Startup probe: verifies database connectivity and baseline initialization.
    """
    db_status = await check_db_health()
    initialized = db_status["status"] != "UNAVAILABLE"

    return {
        "status": "HEALTHY" if initialized else "STARTING",
        "database_connected": initialized,
        "timestamp": time.time(),
    }


@router.get("/health")
@router.get("/api/v1/health")
async def general_health_check():
    """
    Standard comprehensive health status for load balancers & gateway monitoring.
    """
    mongo_health = await check_db_health()
    redis_health = await check_resilient_redis_health()
    realtime_stats = connection_manager.get_stats()

    # Determine overall status
    if mongo_health["status"] == "HEALTHY":
        if redis_health["status"] in ["HEALTHY", "DISABLED"]:
            overall = "healthy"
        else:
            overall = "degraded"
    else:
        overall = "unavailable"

    return {
        "status": overall,
        "mode": degradation_manager.current_mode.value,
        "services": {
            "backend": {
                "status": "healthy",
                "version": settings.app_version,
                "build_sha": settings.build_sha,
                "environment": settings.environment,
            },
            "mongodb": mongo_health,
            "redis": redis_health,
            "realtime": {
                "status": "healthy",
                "transport": "websocket",
                "active_connections": realtime_stats["active_connections"],
                "unique_users": realtime_stats["unique_users"],
                "active_channels": realtime_stats["active_channels"],
            },
        },
    }


@router.get("/api/v1/health/internal")
async def internal_dependency_health(current_user: dict = Depends(get_current_user)):
    """
    Authorized deep inspection endpoint for operations and SRE teams.
    """
    if current_user.get("role") not in ["authority", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Authority access required")

    mongo_health = await check_db_health()
    redis_health = await check_resilient_redis_health()
    metrics = metrics_collector.get_all_metrics()

    return {
        "status": "HEALTHY" if mongo_health["status"] == "HEALTHY" else "DEGRADED",
        "system_mode": degradation_manager.current_mode.value,
        "subsystems": {
            "database": mongo_health,
            "redis": redis_health,
            "realtime": metrics["subsystems"]["realtime"],
            "queues": metrics["subsystems"]["queues"],
            "telemetry": metrics["subsystems"]["telemetry"],
            "incident_operations": metrics["subsystems"]["incident_operations"],
            "ml_and_ai": metrics["subsystems"]["ml_and_ai"],
            "notifications_and_integrations": metrics["subsystems"]["notifications_and_integrations"],
        },
        "golden_signals": metrics["golden_signals"],
    }


@router.get("/metrics")
async def prometheus_metrics():
    """Returns Prometheus text formatted metrics for scraping."""
    prom_data = metrics_collector.export_prometheus()
    return Response(content=prom_data, media_type="text/plain")
