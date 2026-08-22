from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from ..routers.auth import get_current_user, require_role
from ..schemas.notification import (
    DeadLetterRecord,
    DeviceRegisterRequest,
    DeviceTokenRecord,
    NotificationCategory,
    NotificationPriority,
    NotificationRecord,
    ProviderHealthResponse,
    ProviderWebhookPayload,
    UserNotificationPreferences,
    UserPreferencesUpdateRequest,
)
from ..services.notifications import (
    delivery_queue,
    dlq_service,
    notification_center,
    provider_registry,
)

logger = logging.getLogger("toursafe.notifications.router")

router = APIRouter(tags=["notifications"])


# ---------------------------------------------------------------------------
# Authenticated User Notifications & Notification Center
# ---------------------------------------------------------------------------

@router.get("/api/v1/notifications", response_model=List[NotificationRecord])
async def list_notifications(
    unread_only: bool = Query(False, description="Filter only unread notifications"),
    category: Optional[NotificationCategory] = Query(None, description="Filter by category"),
    priority: Optional[NotificationPriority] = Query(None, description="Filter by priority"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    user_id_role: tuple = Depends(get_current_user),
):
    """Retrieve paginated notifications for the authenticated user."""
    user_id, _ = user_id_role
    return await notification_center.get_user_notifications(
        user_id=user_id,
        unread_only=unread_only,
        category=category,
        priority=priority,
        limit=limit,
        skip=skip,
    )


@router.get("/api/v1/notifications/unread-count")
async def get_unread_count(
    user_id_role: tuple = Depends(get_current_user),
):
    """Get the unread notification count for the notification bell badge."""
    user_id, _ = user_id_role
    count = await notification_center.get_unread_count(user_id=user_id)
    return {"unread_count": count}


@router.post("/api/v1/notifications/{notification_id}/read", response_model=NotificationRecord)
async def mark_notification_read(
    notification_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    """Mark an individual notification as read."""
    user_id, _ = user_id_role
    rec = await notification_center.mark_as_read(notification_id=notification_id, user_id=user_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or access denied",
        )
    return rec


@router.post("/api/v1/notifications/read-all")
async def mark_all_notifications_read(
    user_id_role: tuple = Depends(get_current_user),
):
    """Mark all unread notifications as read for current user."""
    user_id, _ = user_id_role
    modified_count = await notification_center.mark_all_as_read(user_id=user_id)
    return {"status": "SUCCESS", "marked_read_count": modified_count}


# ---------------------------------------------------------------------------
# User Notification Preferences
# ---------------------------------------------------------------------------

@router.get("/api/v1/notifications/preferences", response_model=UserNotificationPreferences)
async def get_preferences(
    user_id_role: tuple = Depends(get_current_user),
):
    """Get authenticated user's notification preferences."""
    user_id, role = user_id_role
    return await notification_center.recipient_resolver.get_user_preferences(user_id=user_id, default_role=role)


@router.patch("/api/v1/notifications/preferences", response_model=UserNotificationPreferences)
async def update_preferences(
    req: UserPreferencesUpdateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """Update notification preferences (quiet hours, channel opt-ins)."""
    user_id, role = user_id_role
    return await notification_center.update_preferences(user_id=user_id, req=req, role=role)


# ---------------------------------------------------------------------------
# Push Device Registration
# ---------------------------------------------------------------------------

@router.get("/api/v1/notifications/devices", response_model=List[DeviceTokenRecord])
@router.get("/api/v1/devices", response_model=List[DeviceTokenRecord])
async def list_user_devices(
    user_id_role: tuple = Depends(get_current_user),
):
    """List registered push devices for current user."""
    user_id, _ = user_id_role
    return await notification_center.get_user_devices(user_id=user_id)


@router.post("/api/v1/notifications/devices", response_model=DeviceTokenRecord)
@router.post("/api/v1/devices/register", response_model=DeviceTokenRecord)
async def register_device_token(
    req: DeviceRegisterRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """Register device push notification token."""
    user_id, _ = user_id_role
    return await notification_center.register_device(user_id=user_id, req=req)


@router.delete("/api/v1/notifications/devices/{device_id}")
@router.delete("/api/v1/devices/{device_id}")
async def remove_device_token(
    device_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    """Deregister push device."""
    user_id, _ = user_id_role
    deleted = await notification_center.remove_device(user_id=user_id, device_id=device_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device token not found or already removed",
        )
    return {"status": "DELETED", "device_id": device_id}


# ---------------------------------------------------------------------------
# Provider Webhooks (Delivery Receipts & Status Updates)
# ---------------------------------------------------------------------------

@router.post("/api/v1/notifications/webhooks/{provider}")
async def receive_provider_webhook(
    provider: str,
    payload: ProviderWebhookPayload,
    x_webhook_signature: Optional[str] = Header(None),
):
    """
    Secure webhook endpoint for upstream delivery receipts (Twilio, SendGrid, FCM).
    Ensures provider event idempotency and updates delivery status.
    """
    payload.provider = provider
    if x_webhook_signature:
        payload.signature = x_webhook_signature

    res = await notification_center.process_provider_webhook(payload)
    return res


# ---------------------------------------------------------------------------
# Observability & Metrics
# ---------------------------------------------------------------------------

@router.get("/api/v1/notifications/metrics")
async def get_notification_metrics(
    user_id: str = Depends(require_role("authority", "admin")),
):
    """Get system notification metrics."""
    return await notification_center.get_metrics()


# ---------------------------------------------------------------------------
# Authority Admin Provider & Dead-Letter Management (RBAC: authority/admin)
# ---------------------------------------------------------------------------

@router.get("/api/v1/admin/notifications/providers", response_model=List[ProviderHealthResponse])
async def list_provider_health(
    user_id: str = Depends(require_role("authority", "admin")),
):
    """Inspect status and live health of all notification provider adapters."""
    return await provider_registry.get_all_health_statuses()


@router.get("/api/v1/admin/notifications/failed", response_model=List[DeadLetterRecord])
async def list_dead_letters(
    unresolved_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    user_id: str = Depends(require_role("authority", "admin")),
):
    """List exhausted or permanently failed notifications from Dead Letter Queue."""
    return await dlq_service.list_dead_letters(limit=limit, skip=skip, unresolved_only=unresolved_only)


@router.post("/api/v1/admin/notifications/{dead_letter_id}/retry")
async def retry_dead_letter(
    dead_letter_id: str,
    user_id: str = Depends(require_role("authority", "admin")),
):
    """Manually trigger retry for a dead-letter notification."""
    dlq_item = await dlq_service.resolve_dead_letter(
        dead_letter_id=dead_letter_id,
        action="RETRIED",
        resolved_by=user_id,
        notes="Manual retry triggered by authority administrator",
    )
    if not dlq_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dead letter item not found",
        )
    return {"status": "RETRY_TRIGGERED", "dead_letter": dlq_item}


@router.post("/api/v1/admin/notifications/{dead_letter_id}/cancel")
async def cancel_dead_letter(
    dead_letter_id: str,
    user_id: str = Depends(require_role("authority", "admin")),
):
    """Cancel a dead-letter notification and mark resolved."""
    dlq_item = await dlq_service.resolve_dead_letter(
        dead_letter_id=dead_letter_id,
        action="CANCELLED",
        resolved_by=user_id,
        notes="Cancelled by authority administrator",
    )
    if not dlq_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dead letter item not found",
        )
    return {"status": "CANCELLED", "dead_letter": dlq_item}
