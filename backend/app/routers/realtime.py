import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from ..core.config import settings
from ..core.connection_manager import connection_manager
from ..core.database import get_database
from ..core.realtime_auth import can_subscribe_to_channel, get_default_channels
from ..core.security import decode_token
from ..schemas.realtime import (
    ClientActionType,
    RealtimeEventEnvelope,
    RealtimeEventType,
)
from ..services.realtime_bus import realtime_bus

logger = logging.getLogger("toursafe.realtime.router")

router = APIRouter(tags=["Realtime"])


async def authenticate_websocket(
    websocket: WebSocket,
    token: Optional[str],
) -> Optional[dict]:
    """
    Authenticate a WebSocket connection using JWT.
    Validates token, extracts claims, and optionally loads user context.
    """
    if not token:
        logger.warning("WebSocket connection rejected: Missing token")
        return None

    payload = decode_token(token)
    if not payload:
        logger.warning("WebSocket connection rejected: Invalid or expired token")
        return None

    user_id = payload.get("user_id")
    role = payload.get("role", "tourist")

    if not user_id:
        logger.warning("WebSocket connection rejected: Missing user_id in token payload")
        return None

    # Resolve user profile if available in MongoDB
    user_profile = {"id": user_id, "role": role}
    try:
        db = get_database()
        user_doc = await db.users.find_one({"id": user_id})
        if user_doc:
            if not user_doc.get("is_active", True):
                logger.warning("WebSocket rejected: User %s is inactive", user_id)
                return None
            user_profile["email"] = user_doc.get("email")
            user_profile["full_name"] = user_doc.get("full_name")
            role = user_doc.get("role", role)
            user_profile["role"] = role

        # Check tourist profile id or authority profile id if applicable
        if role == "tourist":
            t_doc = await db.tourist_profiles.find_one({"user_id": user_id})
            if t_doc:
                user_profile["tourist_id"] = t_doc.get("id")
        elif role in ["authority", "admin"]:
            a_doc = await db.authority_profiles.find_one({"user_id": user_id})
            if a_doc:
                user_profile["authority_id"] = a_doc.get("id")
    except Exception as e:
        logger.debug("Database profile lookup note during WS auth: %s", e)

    return {
        "user_id": user_id,
        "role": role,
        "user_profile": user_profile,
    }


@router.websocket("/ws")
@router.websocket("/api/v1/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """
    Primary TourSafe Realtime WebSocket Endpoint.
    Establishes an authenticated full-duplex realtime connection with role-based channel routing.
    """
    await websocket.accept()

    # Step 1: Authenticate connection
    auth_data = await authenticate_websocket(websocket, token)
    if not auth_data:
        # If query param was missing, check briefly for an immediate auth frame
        if not token:
            try:
                auth_msg_raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                auth_msg = json.loads(auth_msg_raw)
                token_from_msg = auth_msg.get("token") or (auth_msg.get("payload") or {}).get("token")
                auth_data = await authenticate_websocket(websocket, token_from_msg)
            except Exception:
                auth_data = None

        if not auth_data:
            rejection_envelope = RealtimeEventEnvelope(
                event_type=RealtimeEventType.SYSTEM_DISCONNECTED.value,
                source="backend",
                payload={"reason": "Authentication failed or token expired", "code": 4001},
            )
            try:
                await websocket.send_text(rejection_envelope.model_dump_json())
            except Exception:
                pass
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    user_id = auth_data["user_id"]
    role = auth_data["role"]
    user_profile = auth_data["user_profile"]

    # Step 2: Assign default authorized channels
    default_channels = get_default_channels(user_id, role, user_profile)

    # Step 3: Register connection in ConnectionManager
    ctx = await connection_manager.register(
        websocket=websocket,
        user_id=user_id,
        role=role,
        initial_channels=default_channels,
        user_profile=user_profile,
    )

    # Step 4: Send connection acknowledgement
    ack_envelope = RealtimeEventEnvelope(
        event_type=RealtimeEventType.SYSTEM_CONNECTED.value,
        source="backend",
        payload={
            "connection_id": ctx.connection_id,
            "user_id": user_id,
            "role": role,
            "channels": list(ctx.channels),
            "connected_at": ctx.connected_at,
        },
    )
    await websocket.send_text(ack_envelope.model_dump_json())

    # Step 5: Connection message loop
    try:
        while True:
            raw_data = await websocket.receive_text()

            # Payload size protection
            if len(raw_data) > settings.ws_max_payload_bytes:
                err_env = RealtimeEventEnvelope(
                    event_type=RealtimeEventType.SYSTEM_ERROR.value,
                    payload={"error": "Payload size exceeded limit"},
                )
                await websocket.send_text(err_env.model_dump_json())
                continue

            ctx.messages_received += 1

            try:
                msg_json = json.loads(raw_data)
            except Exception:
                err_env = RealtimeEventEnvelope(
                    event_type=RealtimeEventType.SYSTEM_ERROR.value,
                    payload={"error": "Invalid JSON format"},
                )
                await websocket.send_text(err_env.model_dump_json())
                continue

            action = msg_json.get("action")
            channel = msg_json.get("channel")

            if action == ClientActionType.PING.value or action == "ping":
                ctx.last_ping_at = datetime.now(timezone.utc).isoformat()
                pong_env = RealtimeEventEnvelope(
                    event_type=RealtimeEventType.SYSTEM_HEARTBEAT.value,
                    payload={"type": "pong", "timestamp": ctx.last_ping_at},
                )
                await websocket.send_text(pong_env.model_dump_json())

            elif action == ClientActionType.SUBSCRIBE.value or action == "subscribe":
                if not channel:
                    err_env = RealtimeEventEnvelope(
                        event_type=RealtimeEventType.SYSTEM_ERROR.value,
                        payload={"error": "Channel name required for subscription"},
                    )
                    await websocket.send_text(err_env.model_dump_json())
                    continue

                # Role-based authorization check
                if can_subscribe_to_channel(user_id, role, channel, user_profile):
                    await connection_manager.subscribe(ctx.connection_id, channel)
                    status_env = RealtimeEventEnvelope(
                        event_type=RealtimeEventType.SYSTEM_STATUS.value,
                        payload={"subscribed": channel, "status": "active"},
                    )
                    await websocket.send_text(status_env.model_dump_json())
                else:
                    logger.warning(
                        "Subscription denied for user %s (role=%s) on channel '%s'",
                        user_id,
                        role,
                        channel,
                    )
                    err_env = RealtimeEventEnvelope(
                        event_type=RealtimeEventType.SYSTEM_ERROR.value,
                        payload={
                            "error": f"Subscription to channel '{channel}' denied: unauthorized role",
                            "channel": channel,
                        },
                    )
                    await websocket.send_text(err_env.model_dump_json())

            elif action == ClientActionType.UNSUBSCRIBE.value or action == "unsubscribe":
                if channel:
                    await connection_manager.unsubscribe(ctx.connection_id, channel)
                    status_env = RealtimeEventEnvelope(
                        event_type=RealtimeEventType.SYSTEM_STATUS.value,
                        payload={"unsubscribed": channel},
                    )
                    await websocket.send_text(status_env.model_dump_json())

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for connection %s", ctx.connection_id)
    except Exception as e:
        logger.warning("WebSocket exception on %s: %s", ctx.connection_id, e)
    finally:
        await connection_manager.disconnect(ctx.connection_id)
