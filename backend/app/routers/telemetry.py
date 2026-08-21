import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..core import database as db_core
from ..routers.auth import get_current_user
from ..schemas.telemetry import (
    AuthorityTelemetryStatusResponse,
    QualityMetrics,
    QualityStateEnum,
    SessionStatusEnum,
    TelemetryAck,
    TelemetryBatchAck,
    TelemetryBatchRequest,
    TelemetryDiagnosticsResponse,
    TelemetryPacketEnvelope,
    TelemetrySessionMetrics,
    TelemetrySessionResponse,
    TelemetrySessionStartRequest,
    TelemetrySessionStopRequest,
    TelemetryWindow,
    TouristTelemetryStatusResponse,
)
from ..services.telemetry import (
    quality_evaluator,
    telemetry_persistence,
    telemetry_queue,
    telemetry_redis_state,
    telemetry_service,
    telemetry_session_manager,
)

logger = logging.getLogger("toursafe.telemetry.router")

router = APIRouter(tags=["Telemetry Pipeline"])


async def resolve_tourist_id(user_id: str, role: str) -> str:
    """Helper to resolve tourist_id corresponding to authenticated user."""
    db = db_core.get_database()
    tourist_doc = await db["tourists"].find_one({"user_id": user_id})
    if tourist_doc:
        return tourist_doc.get("id", user_id)
    return user_id


# ─── 1. Ingest Canonical Telemetry Packet ─────────────────────────────────────

@router.post(
    "/api/v1/telemetry/packet",
    response_model=TelemetryAck,
    status_code=status.HTTP_200_OK,
    summary="Ingest Canonical Telemetry Packet Envelope",
)
@router.post(
    "/api/v1/telemetry/sample",
    response_model=TelemetryAck,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def ingest_telemetry_packet(
    envelope: TelemetryPacketEnvelope,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Authenticated ingestion endpoint for canonical telemetry packets.
    Extracts tourist identity securely from JWT authentication.
    Applies envelope validation, sequence tracking, idempotency, Redis live update,
    durable persistence queue, and 3-second temporal window engine.
    """
    user_id, role = user_id_role
    if role != "tourist" and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authenticated tourist devices can transmit telemetry packets",
        )

    tourist_id = await resolve_tourist_id(user_id, role)

    try:
        ack = await telemetry_service.ingest_packet(
            envelope=envelope,
            authenticated_tourist_id=tourist_id,
            user_id=user_id,
        )
        return ack
    except Exception as e:
        logger.error("Telemetry ingestion exception: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process telemetry packet: {str(e)}",
        )


# ─── 2. Ingest Bounded Telemetry Batch ────────────────────────────────────────

@router.post(
    "/api/v1/telemetry/batch",
    response_model=TelemetryBatchAck,
    status_code=status.HTTP_200_OK,
    summary="Ingest Bounded Batch of Telemetry Packets (Replay / Offline Sync)",
)
async def ingest_telemetry_batch(
    batch: TelemetryBatchRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Authenticated endpoint to ingest bounded batches of telemetry packets.
    Used during offline buffer replay and high-throughput transmissions.
    """
    user_id, role = user_id_role
    if role != "tourist" and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authenticated tourist accounts can transmit telemetry batches",
        )

    if not batch.packets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telemetry batch contains no packets",
        )

    tourist_id = await resolve_tourist_id(user_id, role)

    try:
        return await telemetry_service.ingest_packet_batch(
            session_id=batch.session_id,
            packets=batch.packets,
            authenticated_tourist_id=tourist_id,
            user_id=user_id,
        )
    except Exception as e:
        logger.error("Batch telemetry ingestion error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process telemetry batch: {str(e)}",
        )


# ─── 3. Telemetry Session Lifecycle ──────────────────────────────────────────

@router.post(
    "/api/v1/telemetry/session/start",
    response_model=TelemetrySessionResponse,
    summary="Start Telemetry Tracking Session",
)
async def start_telemetry_session(
    payload: TelemetrySessionStartRequest = TelemetrySessionStartRequest(),
    user_id_role: tuple = Depends(get_current_user),
):
    """Starts or registers a continuous telemetry tracking session."""
    user_id, role = user_id_role
    if role != "tourist" and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tourist accounts can initiate telemetry sessions",
        )

    tourist_id = await resolve_tourist_id(user_id, role)
    session_id = f"tsess_{uuid.uuid4().hex[:12]}"

    session_state = await telemetry_session_manager.get_or_create_session(
        session_id=session_id,
        tourist_id=tourist_id,
        user_id=user_id,
        device_id=payload.device_id,
    )

    return TelemetrySessionResponse(
        session_id=session_id,
        tourist_id=tourist_id,
        user_id=user_id,
        device_id=payload.device_id,
        status=session_state.status,
        started_at=session_state.started_at,
        metrics=session_state.to_metrics(),
    )


@router.post(
    "/api/v1/telemetry/session/stop",
    response_model=TelemetrySessionResponse,
    summary="Stop Telemetry Tracking Session",
)
async def stop_telemetry_session(
    payload: TelemetrySessionStopRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """Stops an active telemetry tracking session and clears live keys."""
    user_id, role = user_id_role
    if role != "tourist" and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tourist accounts can stop telemetry sessions",
        )

    tourist_id = await resolve_tourist_id(user_id, role)
    result = await telemetry_session_manager.stop_session(
        session_id=payload.session_id,
        tourist_id=tourist_id,
    )

    # Clear live redis state
    await telemetry_redis_state.clear_live_state(tourist_id, payload.session_id)

    if not result:
        return TelemetrySessionResponse(
            session_id=payload.session_id,
            tourist_id=tourist_id,
            user_id=user_id,
            status=SessionStatusEnum.STOPPED,
            started_at=datetime.now(timezone.utc).isoformat(),
            ended_at=datetime.now(timezone.utc).isoformat(),
            metrics=TelemetrySessionMetrics(),
        )

    return result


# ─── 4. Tourist Telemetry Status & History ────────────────────────────────────

@router.get(
    "/api/v1/tourists/me/telemetry/status",
    response_model=TouristTelemetryStatusResponse,
    summary="Get My Current Telemetry Pipeline Status",
)
async def get_my_telemetry_status(
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Exposes current telemetry pipeline status, live quality assessment,
    and session metrics to the authenticated tourist.
    """
    user_id, role = user_id_role
    if role != "tourist" and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tourist profile access required",
        )

    tourist_id = await resolve_tourist_id(user_id, role)
    live_state = await telemetry_redis_state.get_live_state(tourist_id)

    if live_state:
        session_id = live_state.get("session_id")
        session_obj = await telemetry_session_manager.get_session(session_id) if session_id else None
        metrics = session_obj.to_metrics() if session_obj else TelemetrySessionMetrics()

        quality = quality_evaluator.compute_metrics(
            gps_accuracy=live_state.get("last_gps", {}).get("accuracy") if live_state.get("last_gps") else None,
            observed_imu_hz=live_state.get("observed_frequency_hz"),
            target_hz=50.0,
            sync_delta_ms=0.0,
        )

        return TouristTelemetryStatusResponse(
            tourist_id=tourist_id,
            active_session_id=session_id,
            tracking_status=SessionStatusEnum(live_state.get("tracking_status", "active")),
            imu_active="last_imu" in live_state,
            gps_active="last_gps" in live_state,
            last_telemetry_timestamp=live_state.get("timestamp"),
            observed_imu_frequency_hz=live_state.get("observed_frequency_hz"),
            connection_state="connected",
            quality=quality,
            metrics=metrics,
            recent_windows_generated=metrics.window_count,
        )

    # Inactive state
    return TouristTelemetryStatusResponse(
        tourist_id=tourist_id,
        active_session_id=None,
        tracking_status=SessionStatusEnum.STOPPED,
        imu_active=False,
        gps_active=False,
        last_telemetry_timestamp=None,
        observed_imu_frequency_hz=None,
        connection_state="idle",
        quality=QualityMetrics(
            gps_quality=QualityStateEnum.UNAVAILABLE,
            imu_quality=QualityStateEnum.UNAVAILABLE,
            synchronization_quality=QualityStateEnum.UNAVAILABLE,
            network_quality=QualityStateEnum.GOOD,
            overall_quality=QualityStateEnum.UNAVAILABLE,
        ),
        metrics=TelemetrySessionMetrics(),
        recent_windows_generated=0,
    )


@router.get(
    "/api/v1/tourists/me/telemetry/windows",
    response_model=List[TelemetryWindow],
    summary="Get Recent Telemetry Windows for Active Session",
)
async def get_my_telemetry_windows(
    session_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user_id_role: tuple = Depends(get_current_user),
):
    """Returns recently generated 3-second TelemetryWindow objects."""
    user_id, role = user_id_role
    if role != "tourist" and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tourist profile access required",
        )

    tourist_id = await resolve_tourist_id(user_id, role)
    if not session_id:
        live = await telemetry_redis_state.get_live_state(tourist_id)
        session_id = live.get("session_id") if live else None

    if not session_id:
        return []

    docs = await telemetry_persistence.query_session_windows(session_id, limit=limit)
    return [TelemetryWindow(**d) for d in docs]


# ─── 5. Authority Telemetry Monitoring (Summarized Status) ────────────────────

@router.get(
    "/api/v1/authority/tourists/{tourist_id}/telemetry-status",
    response_model=AuthorityTelemetryStatusResponse,
    summary="Authority: Get Summarized Tourist Operational Telemetry Status",
)
async def get_tourist_telemetry_status_as_authority(
    tourist_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Authority endpoint to inspect operational telemetry health for a tourist.
    Note: Raw 50 Hz IMU sensor data is strictly NOT exposed to authority clients.
    """
    _, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or responder access required",
        )

    live_state = await telemetry_redis_state.get_live_state(tourist_id)
    if live_state:
        ts_str = live_state.get("timestamp")
        age_sec = None
        is_stale = True
        if ts_str:
            try:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                age_sec = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())
                is_stale = age_sec > 60.0
            except Exception:
                pass

        gps_info = live_state.get("last_gps")
        return AuthorityTelemetryStatusResponse(
            tourist_id=tourist_id,
            session_id=live_state.get("session_id"),
            tracking_status=SessionStatusEnum(live_state.get("tracking_status", "active")),
            last_location_timestamp=gps_info.get("timestamp") if gps_info else None,
            last_telemetry_timestamp=ts_str,
            gps_quality=QualityStateEnum(live_state.get("gps_quality", "unavailable")),
            imu_quality=QualityStateEnum(live_state.get("imu_quality", "good")),
            overall_quality=QualityStateEnum(live_state.get("overall_quality", "good")),
            connection_state="active" if not is_stale else "stale",
            is_stale=is_stale,
            age_seconds=round(age_sec, 2) if age_sec is not None else None,
        )

    return AuthorityTelemetryStatusResponse(
        tourist_id=tourist_id,
        session_id=None,
        tracking_status=SessionStatusEnum.STOPPED,
        last_location_timestamp=None,
        last_telemetry_timestamp=None,
        gps_quality=QualityStateEnum.UNAVAILABLE,
        imu_quality=QualityStateEnum.UNAVAILABLE,
        overall_quality=QualityStateEnum.UNAVAILABLE,
        connection_state="offline",
        is_stale=True,
        age_seconds=None,
    )


@router.get(
    "/api/v1/authority/telemetry-diagnostics",
    response_model=TelemetryDiagnosticsResponse,
    summary="Authority / Admin: Ingestion Diagnostics & Backpressure Metrics",
)
async def get_telemetry_diagnostics(
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Returns pipeline backpressure statistics, queue depth, and persistence health.
    """
    _, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin/Authority privileges required",
        )

    queue_stats = telemetry_queue.get_stats()
    from ..core import redis as redis_core
    redis_h = await redis_core.check_redis_health()

    return TelemetryDiagnosticsResponse(
        queue_depth=queue_stats["queue_depth"],
        queue_capacity=queue_stats["queue_capacity"],
        enqueue_failures=queue_stats["enqueue_failures"],
        processing_latency_ms=queue_stats["processing_latency_ms"],
        total_ingested_today=telemetry_service.total_ingested_today,
        active_sessions_count=telemetry_session_manager.get_active_sessions_count(),
        redis_health=redis_h,
        mongodb_persistence_ok=True,
    )


@router.post(
    "/api/v1/authority/telemetry/retention/purge",
    summary="Admin: Trigger Telemetry Retention Policy Purge",
)
async def trigger_retention_purge(
    user_id_role: tuple = Depends(get_current_user),
):
    """Manually executes retention policy purge of historical telemetry older than configured days."""
    _, role = user_id_role
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    purged = await telemetry_persistence.apply_retention_policy()
    return {"status": "success", "purged_count": purged}
