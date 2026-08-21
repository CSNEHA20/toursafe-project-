"""
TourSafe ML & Anomaly Inference Router.
Exposes internal ML observability/health endpoints, dev window testing diagnostics,
and authority anomaly episode feeds.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from .auth import get_current_user, require_role
from ..schemas.ml import InferenceResult, MLHealthResponse
from ..schemas.telemetry import TelemetryWindow
from ..services.ml.engine import ml_inference_engine
from ..services.ml.loader import model_loader
from ..services.ml.metrics import ml_metrics_tracker
from ..services.ml.persistence import anomaly_persistence

router = APIRouter(tags=["ML & Anomaly Inference"])


@router.get(
    "/api/v1/internal/ml/health",
    response_model=MLHealthResponse,
    summary="ML Service Health & Observability",
)
async def get_ml_health():
    """
    Returns real-time ML inference service status, model metadata, latency percentiles,
    queue depth, and throughput rate.
    """
    return ml_metrics_tracker.get_health_summary(
        queue_depth=ml_inference_engine.get_queue_depth(),
        queue_capacity=ml_inference_engine.queue_capacity,
    )


@router.post(
    "/api/v1/internal/ml/infer-window",
    response_model=InferenceResult,
    summary="Development Diagnostic Window Inference",
)
async def dev_infer_window(
    window: TelemetryWindow,
    user_id: str = Depends(require_role("admin", "authority", "dev")),
):
    """
    Development-only endpoint allowing authorized engineers to submit a single
    TelemetryWindow directly for synchronous inference and diagnostic breakdown.
    """
    result = await ml_inference_engine.process_single_window(window)
    return result


@router.get(
    "/api/v1/anomalies/active",
    summary="Get Active Anomaly Episodes",
)
async def get_active_anomalies(
    user_id: str = Depends(require_role("authority", "admin")),
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    Returns currently active motion/sensor anomaly episodes for the authority command center.
    """
    episodes = await anomaly_persistence.get_active_episodes(limit=limit)
    return {"status": "success", "count": len(episodes), "episodes": episodes}


@router.get(
    "/api/v1/anomalies/history",
    summary="Get Historical Anomaly Episodes",
)
async def get_anomaly_history(
    tourist_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(require_role("authority", "admin")),
):
    """
    Returns historical anomaly records with filtering and pagination.
    """
    episodes = await anomaly_persistence.get_historical_episodes(
        tourist_id=tourist_id,
        limit=limit,
    )
    return {"status": "success", "count": len(episodes), "episodes": episodes}
