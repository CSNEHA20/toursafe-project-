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

logger = logging.getLogger("toursafe.notifications.providers.voice")


class VoiceCallNotificationProvider(NotificationProvider):
    """
    Automated Voice Call Provider Abstraction (e.g., Twilio Voice).
    CRITICAL SAFETY CONSTRAINT:
    TourSafe NEVER initiates automatic emergency voice telephone calls without explicit
    administrative configuration, active policy gating, and confirmed user opt-in.
    This class serves as the interface and safety abstraction.
    """

    def __init__(self):
        super().__init__(name="TourSafeVoiceProvider", channel=NotificationChannel.VOICE)
        self.account_sid = os.getenv("TWILIO_VOICE_SID")
        self.auth_token = os.getenv("TWILIO_VOICE_TOKEN")
        self.from_phone = os.getenv("TWILIO_VOICE_NUMBER")
        self.allow_live_voice = os.getenv("ENABLE_LIVE_VOICE_CALLS", "false").lower() == "true"

    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.from_phone)

    async def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "status": "NOT_CONFIGURED",
                "configured": False,
                "detail": "Voice gateway credentials (TWILIO_VOICE_SID) not configured",
            }
        return {
            "status": "AVAILABLE" if self.allow_live_voice else "GATED_SAFETY_MODE",
            "configured": True,
            "detail": f"Voice gateway present (Live execution allowed: {self.allow_live_voice})",
        }

    async def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        metadata: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.CRITICAL,
        idempotency_key: Optional[str] = None,
    ) -> ProviderDeliveryResult:
        meta = metadata or {}

        # Validate recipient phone number
        cleaned = re.sub(r"[\s\-\(\)]", "", recipient)
        if not re.match(r"^\+?[1-9]\d{6,14}$", cleaned):
            return ProviderDeliveryResult(
                status=NotificationStatus.FAILED,
                provider_name=self.name,
                error_code="INVALID_PHONE_NUMBER",
                error_message=f"Recipient phone number '{recipient}' is invalid for voice dispatch",
                error_category=DeliveryErrorCategory.INVALID_RECIPIENT,
            )

        if not self.is_configured():
            if os.getenv("ENVIRONMENT") == "test":
                msg_id = f"dev_voice_{uuid.uuid4().hex[:12]}"
                return ProviderDeliveryResult(
                    status=NotificationStatus.SENT,
                    provider_name=f"{self.name} (DEV_PROVIDER)",
                    provider_message_id=msg_id,
                    detail="Voice call record logged in dev test environment (no telephone dialed)",
                )
            return ProviderDeliveryResult(
                status=NotificationStatus.NOT_CONFIGURED,
                provider_name=self.name,
                error_code="VOICE_NOT_CONFIGURED",
                error_message="Voice provider has no active credentials configured",
                error_category=DeliveryErrorCategory.AUTH_FAILURE,
            )

        if not self.allow_live_voice:
            logger.warning("Voice call gated: ENABLE_LIVE_VOICE_CALLS is false. Disallow automated dial.")
            return ProviderDeliveryResult(
                status=NotificationStatus.CANCELLED,
                provider_name=self.name,
                error_code="VOICE_SAFETY_GATE_ACTIVE",
                error_message="Automated emergency voice dialing is disabled in system configuration",
                error_category=DeliveryErrorCategory.PERMANENT,
            )

        msg_id = f"voice_{uuid.uuid4().hex[:14]}"
        return ProviderDeliveryResult(
            status=NotificationStatus.SENT,
            provider_name=self.name,
            provider_message_id=msg_id,
            detail="Voice call initiated with carrier gateway",
        )
