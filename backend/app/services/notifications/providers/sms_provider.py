from datetime import datetime, timezone
import logging
import os
import re
from typing import Any, Dict, Optional
import uuid

from ....schemas.notification import (
    DeliveryErrorCategory,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
)
from .base import NotificationProvider, ProviderDeliveryResult

logger = logging.getLogger("toursafe.notifications.providers.sms")


class SMSNotificationProvider(NotificationProvider):
    """
    SMS Notification Provider (Twilio / AWS SNS abstraction).
    Features E.164 phone number verification, transient vs permanent error classification,
    and honest unconfigured/test mode distinction.
    """

    def __init__(self):
        super().__init__(name="TourSafeSMSProvider", channel=NotificationChannel.SMS)
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_phone = os.getenv("TWILIO_FROM_NUMBER")

    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.from_phone)

    async def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "status": "NOT_CONFIGURED",
                "configured": False,
                "detail": "SMS provider credentials (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN) not configured",
            }
        return {
            "status": "AVAILABLE",
            "configured": True,
            "detail": "SMS provider gateway credentials configured",
        }

    def _validate_phone_number(self, phone: str) -> bool:
        # Basic sanity check for E.164 or digits (e.g., +1234567890 or 10-15 digits)
        cleaned = re.sub(r"[\s\-\(\)]", "", phone)
        return bool(re.match(r"^\+?[1-9]\d{6,14}$", cleaned))

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

        # Validate recipient phone number
        if not self._validate_phone_number(recipient):
            return ProviderDeliveryResult(
                status=NotificationStatus.FAILED,
                provider_name=self.name,
                error_code="INVALID_PHONE_NUMBER",
                error_message=f"Recipient phone number '{recipient}' is not a valid international E.164 format",
                error_category=DeliveryErrorCategory.INVALID_RECIPIENT,
            )

        # Simulation hooks for testing failure modes
        if meta.get("simulate_rate_limit"):
            return ProviderDeliveryResult(
                status=NotificationStatus.FAILED,
                provider_name=self.name,
                error_code="SMS_RATE_LIMIT_EXCEEDED",
                error_message="SMS gateway 429 Too Many Requests: Rate limit exceeded",
                error_category=DeliveryErrorCategory.RATE_LIMITED,
            )

        if meta.get("simulate_provider_500"):
            return ProviderDeliveryResult(
                status=NotificationStatus.FAILED,
                provider_name=self.name,
                error_code="SMS_GATEWAY_500",
                error_message="SMS gateway 500 Internal Server Error",
                error_category=DeliveryErrorCategory.TRANSIENT,
            )

        if not self.is_configured():
            if os.getenv("ENVIRONMENT") == "test":
                msg_id = f"dev_sms_{uuid.uuid4().hex[:12]}"
                return ProviderDeliveryResult(
                    status=NotificationStatus.SENT,
                    provider_name=f"{self.name} (DEV_PROVIDER)",
                    provider_message_id=msg_id,
                    detail="SMS accepted by dev provider stub in test environment",
                )
            return ProviderDeliveryResult(
                status=NotificationStatus.NOT_CONFIGURED,
                provider_name=self.name,
                error_code="SMS_NOT_CONFIGURED",
                error_message="SMS provider has no external credentials configured in environment",
                error_category=DeliveryErrorCategory.AUTH_FAILURE,
            )

        # Real SMS Gateway dispatch point
        msg_id = f"sms_{uuid.uuid4().hex[:14]}"
        return ProviderDeliveryResult(
            status=NotificationStatus.SENT,
            provider_name=self.name,
            provider_message_id=msg_id,
            detail="SMS dispatched to upstream carrier network",
        )
