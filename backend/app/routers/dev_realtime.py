import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from ..core.config import settings
from ..core.connection_manager import connection_manager
from ..dependencies import oauth2_scheme
from ..core.security import decode_token
from ..schemas.realtime import (
    DevTestEventRequest,
    RealtimeEventEnvelope,
    ConnectionStatsResponse,
)
from ..services.realtime_bus import realtime_bus

logger = logging.getLogger("toursafe.dev.realtime")

router = APIRouter(prefix="/api/v1/dev/realtime", tags=["Dev Realtime"])


async def get_current_dev_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Dependency ensuring token is valid and environment is development/testing."""
    if settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Development endpoints are disabled in production environment.",
        )

    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        )
    return payload


@router.post("/test-event", response_model=RealtimeEventEnvelope)
async def publish_test_event(
    request: DevTestEventRequest,
    current_user: dict = Depends(get_current_dev_user),
):
    """
    Publish a test event across the TourSafe Realtime Event Bus.
    Only available in development/testing environments.
    """
    logger.info(
        "Dev user %s triggering test event '%s'",
        current_user.get("user_id"),
        request.event_type,
    )

    envelope = await realtime_bus.publish_event(
        event_type=request.event_type,
        payload=request.payload,
        channel=request.channel,
        target_user_id=request.target_user_id,
        target_role=request.target_role,
        source=f"dev_test:{current_user.get('user_id')}",
        version=1,
    )

    return envelope


@router.get("/stats", response_model=ConnectionStatsResponse)
async def get_realtime_connection_stats(
    current_user: dict = Depends(get_current_dev_user),
):
    """
    Retrieve real-time telemetry on active WebSocket connections and channel distribution.
    """
    stats = connection_manager.get_stats()
    return ConnectionStatsResponse(
        active_connections=stats["active_connections"],
        unique_users=stats["unique_users"],
        active_channels=stats["active_channels"],
        channels=stats["channels"],
        roles_connected=stats["roles_connected"],
    )
