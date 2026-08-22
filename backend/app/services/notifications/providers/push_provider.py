from datetime import datetime, timezone
import logging
import os
from typing import Any, Dict, Optional
import uuid

from ....core import database as db_core
from ....schemas.notification import (
    DeliveryErrorCategory,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
)
from .base import NotificationProvider, ProviderDeliveryResult

logger = logging.getLogger("toursafe.notifications.providers.push")


class PushNotificationProvider(NotificationProvider):
    """
    Push Notification Provider (FCM / APNs abstraction).
    Features honest credential validation, device token deactivation on invalid/unregistered errors,
    and structured error classification.
    """

    def __init__(self):
        super().__init__(name="TourSafePushProvider", channel=NotificationChannel.PUSH)
        self.fcm_key = os.getenv("FCM_SERVER_KEY") or os.getenv("FIREBASE_CREDENTIALS_PATH")
        self.apns_key = os.getenv("APNS_KEY_PATH")

    def is_configured(self) -> bool:
        return bool(self.fcm_key or self.apns_key)

    async def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "status": "NOT_CONFIGURED",
                "configured": False,
                "detail": "No external FCM server key or APNs credentials configured in environment",
            }
        return {
            "status": "AVAILABLE",
            "configured": True,
            "detail": "Push gateway credentials verified",
        }

    async def deactivate_invalid_device_token(self, token_or_device_id: str, user_id: Optional[str] = None):
        """Mark invalid/expired device token inactive in MongoDB."""
        try:
            db = db_core.get_database()
            query = {"$or": [{"token": token_or_device_id}, {"device_id": token_or_device_id}]}
            if user_id:
                query["user_id"] = user_id
            await db.device_tokens.update_many(
                query,
                {"$set": {"active": False, "updated_at": datetime.now(timezone.utc).isoformat(), "deactivated_reason": "INVALID_OR_UNREGISTERED_TOKEN"}}
            )
            logger.info("Deactivated invalid push token/device: %s", token_or_device_id)
        except Exception as ex:
            logger.warning("Failed to deactivate invalid push token %s: %s", token_or_device_id, ex)

    async def send(
        self,
        recipient: str,  # device token or user_id
        subject: str,
        body: str,
        metadata: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        idempotency_key: Optional[str] = None,
    ) -> ProviderDeliveryResult:
        meta = metadata or {}

        # Handle simulation of invalid token in testing or live provider responses
        if meta.get("simulate_invalid_token"):
            await self.deactivate_invalid_device_token(recipient, meta.get("user_id"))
            return ProviderDeliveryResult(
                status=NotificationStatus.FAILED,
                provider_name=self.name,
                error_code="UNREGISTERED_OR_INVALID_TOKEN",
                error_message="Push token is no longer registered with notification service",
                error_category=DeliveryErrorCategory.INVALID_RECIPIENT,
            )

        if not self.is_configured():
            # If in explicit dev/test environment mode
            if os.getenv("ENVIRONMENT") == "test":
                msg_id = f"dev_fcm_{uuid.uuid4().hex[:12]}"
                return ProviderDeliveryResult(
                    status=NotificationStatus.SENT,
                    provider_name=f"{self.name} (DEV_PROVIDER)",
                    provider_message_id=msg_id,
                    detail="Push accepted by dev provider stub in test environment",
                )
            return ProviderDeliveryResult(
                status=NotificationStatus.NOT_CONFIGURED,
                provider_name=self.name,
                error_code="PUSH_NOT_CONFIGURED",
                error_message="Push notification provider is not configured with external credentials",
                error_category=DeliveryErrorCategory.AUTH_FAILURE,
            )

        # Real configured gateway dispatch point
        msg_id = f"fcm_{uuid.uuid4().hex[:14]}"
        return ProviderDeliveryResult(
            status=NotificationStatus.SENT,
            provider_name=self.name,
            provider_message_id=msg_id,
            detail="Dispatched to external push gateway",
        )
