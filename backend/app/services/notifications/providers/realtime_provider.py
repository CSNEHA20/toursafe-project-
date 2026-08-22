from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
import uuid

from ....schemas.notification import (
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
)
from ...realtime_bus import realtime_bus
from .base import NotificationProvider, ProviderDeliveryResult

logger = logging.getLogger("toursafe.notifications.providers.realtime")


class RealtimeNotificationProvider(NotificationProvider):
    """
    Realtime notification provider.
    Dispatches instant notification envelopes across WebSocket connections.
    """

    def __init__(self):
        super().__init__(name="TourSafeRealtimeProvider", channel=NotificationChannel.REALTIME)

    def is_configured(self) -> bool:
        return True

    async def health_check(self) -> Dict[str, Any]:
        stats = realtime_bus.manager.get_stats()
        return {
            "status": "AVAILABLE",
            "configured": True,
            "detail": f"Realtime event bus active with {stats.get('total_connections', 0)} connections",
            "stats": stats,
        }

    async def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        metadata: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        idempotency_key: Optional[str] = None,
    ) -> ProviderDeliveryResult:
        meta = metadata or {}
        event_payload = {
            "notification_id": meta.get("notification_id", f"notif_{uuid.uuid4().hex[:12]}"),
            "title": subject,
            "body": body,
            "priority": priority.value if hasattr(priority, "value") else str(priority),
            "category": meta.get("category", "SYSTEM"),
            "incident_id": meta.get("incident_id"),
            "deep_link": meta.get("deep_link"),
            "data": meta.get("data", {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        channel = meta.get("channel_override")
        role = meta.get("role_target")

        try:
            envelope = await realtime_bus.publish_event(
                event_type="notification.created",
                payload=event_payload,
                channel=channel,
                target_user_id=recipient if not channel and not role else None,
                target_role=role,
                source="notification_service",
            )
            return ProviderDeliveryResult(
                status=NotificationStatus.DELIVERED,
                provider_name=self.name,
                provider_message_id=envelope.event_id,
                detail="Dispatched via Realtime WebSocket EventBus",
            )
        except Exception as ex:
            logger.error("Realtime dispatch failed for recipient %s: %s", recipient, ex)
            return ProviderDeliveryResult(
                status=NotificationStatus.FAILED,
                provider_name=self.name,
                error_code="REALTIME_DISPATCH_ERROR",
                error_message=str(ex),
            )
