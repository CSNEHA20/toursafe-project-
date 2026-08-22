from abc import abstractmethod
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
import uuid

from ....schemas.integrations import (
    IntegrationConfig,
    IntegrationHealthStatus,
    IntegrationStatus,
    IntegrationType,
)
from ....schemas.notification import NotificationPriority, NotificationStatus
from ..circuit_breaker import CircuitBreaker
from .base import IntegrationAdapter

logger = logging.getLogger("toursafe.integrations.adapters.comms")


class SMSAdapter(IntegrationAdapter):
    """
    SMS Adapter interface.
    Normalizes SMS dispatch, delivery verification, and failure modes across Twilio, AWS SNS, Sinch, etc.
    """

    def __init__(
        self,
        provider_name: str = "DEV_SMS_ADAPTER",
        is_real_provider: bool = False,
        config: Optional[IntegrationConfig] = None,
    ):
        super().__init__(
            provider_name=provider_name,
            integration_type=IntegrationType.SMS,
            is_real_provider=is_real_provider,
            config=config or IntegrationConfig(provider_name=provider_name, integration_type=IntegrationType.SMS),
        )

    @property
    def capabilities(self) -> List[str]:
        return ["sms_send", "sms_status", "delivery_receipt", "shortcode_support"]

    async def initialize(self) -> None:
        logger.info("SMSAdapter (%s): Initialized.", self.provider_name)

    async def shutdown(self) -> None:
        pass

    async def execute_health_check(self) -> IntegrationHealthStatus:
        status = self.get_health_status()
        status.latency_ms = 15.0
        status.is_healthy = True
        status.detail = f"SMS Gateway '{self.provider_name}' reachable"
        return status

    async def send_sms(
        self,
        recipient_phone: str,
        message_body: str,
        sender_id: Optional[str] = "TOURSAFE",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        start_t = time.time()
        await self.circuit_breaker.before_execution()

        # Check phone format
        clean_phone = recipient_phone.replace(" ", "").replace("-", "")
        if not clean_phone.startswith("+") and not clean_phone.isdigit():
            raise ValueError(f"Invalid phone number format: {recipient_phone}")

        msg_id = f"sms_{uuid.uuid4().hex[:14]}"
        latency_ms = (time.time() - start_t) * 1000.0
        await self.circuit_breaker.record_success()
        self.record_request_metrics(latency_ms, is_success=True)

        return {
            "success": True,
            "status": "SENT",
            "provider": self.provider_name,
            "provider_message_id": msg_id,
            "recipient": recipient_phone,
            "characters_count": len(message_body),
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
        }


class VoiceAdapter(IntegrationAdapter):
    """
    Voice Call Adapter interface (Twilio Voice, Amazon Connect, Asterisk IVR).
    """

    def __init__(
        self,
        provider_name: str = "DEV_VOICE_ADAPTER",
        is_real_provider: bool = False,
        config: Optional[IntegrationConfig] = None,
    ):
        super().__init__(
            provider_name=provider_name,
            integration_type=IntegrationType.VOICE,
            is_real_provider=is_real_provider,
            config=config or IntegrationConfig(provider_name=provider_name, integration_type=IntegrationType.VOICE),
        )

    @property
    def capabilities(self) -> List[str]:
        return ["voice_outbound_call", "text_to_speech", "ivr_flow", "call_recording"]

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def execute_health_check(self) -> IntegrationHealthStatus:
        status = self.get_health_status()
        status.latency_ms = 18.0
        status.is_healthy = True
        status.detail = f"Voice Gateway '{self.provider_name}' operational"
        return status

    async def initiate_call(
        self,
        recipient_phone: str,
        tts_message: str,
        emergency_priority: bool = False,
    ) -> Dict[str, Any]:
        start_t = time.time()
        await self.circuit_breaker.before_execution()

        call_id = f"call_{uuid.uuid4().hex[:14]}"
        latency_ms = (time.time() - start_t) * 1000.0
        await self.circuit_breaker.record_success()
        self.record_request_metrics(latency_ms, is_success=True)

        return {
            "success": True,
            "status": "QUEUED",
            "provider": self.provider_name,
            "provider_call_id": call_id,
            "recipient": recipient_phone,
            "is_emergency": emergency_priority,
            "initiated_at": datetime.now(timezone.utc).isoformat(),
        }


class EmailAdapter(IntegrationAdapter):
    """
    Email Adapter interface (Sendgrid, AWS SES, Mailgun, SMTP).
    """

    def __init__(
        self,
        provider_name: str = "DEV_EMAIL_ADAPTER",
        is_real_provider: bool = False,
        config: Optional[IntegrationConfig] = None,
    ):
        super().__init__(
            provider_name=provider_name,
            integration_type=IntegrationType.EMAIL,
            is_real_provider=is_real_provider,
            config=config or IntegrationConfig(provider_name=provider_name, integration_type=IntegrationType.EMAIL),
        )

    @property
    def capabilities(self) -> List[str]:
        return ["email_send", "template_rendering", "bounce_tracking", "attachment_support"]

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def execute_health_check(self) -> IntegrationHealthStatus:
        status = self.get_health_status()
        status.latency_ms = 12.0
        status.is_healthy = True
        status.detail = f"Email SMTP/API '{self.provider_name}' operational"
        return status

    async def send_email(
        self,
        recipient_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        start_t = time.time()
        await self.circuit_breaker.before_execution()

        if "@" not in recipient_email:
            raise ValueError(f"Invalid email address: {recipient_email}")

        email_id = f"mail_{uuid.uuid4().hex[:14]}"
        latency_ms = (time.time() - start_t) * 1000.0
        await self.circuit_breaker.record_success()
        self.record_request_metrics(latency_ms, is_success=True)

        return {
            "success": True,
            "status": "SENT",
            "provider": self.provider_name,
            "provider_email_id": email_id,
            "recipient": recipient_email,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }


class PushAdapter(IntegrationAdapter):
    """
    Push Notification Adapter interface (Firebase Cloud Messaging / Apple APNS).
    Integrates with Prompt 14 push infrastructure.
    """

    def __init__(
        self,
        provider_name: str = "DEV_PUSH_ADAPTER",
        is_real_provider: bool = False,
        config: Optional[IntegrationConfig] = None,
    ):
        super().__init__(
            provider_name=provider_name,
            integration_type=IntegrationType.PUSH,
            is_real_provider=is_real_provider,
            config=config or IntegrationConfig(provider_name=provider_name, integration_type=IntegrationType.PUSH),
        )

    @property
    def capabilities(self) -> List[str]:
        return ["fcm_push", "apns_push", "topic_broadcast", "data_payloads"]

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def execute_health_check(self) -> IntegrationHealthStatus:
        status = self.get_health_status()
        status.latency_ms = 8.0
        status.is_healthy = True
        status.detail = f"Push Gateway '{self.provider_name}' connected"
        return status

    async def send_push(
        self,
        device_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        priority: str = "HIGH",
    ) -> Dict[str, Any]:
        start_t = time.time()
        await self.circuit_breaker.before_execution()

        push_id = f"push_{uuid.uuid4().hex[:14]}"
        latency_ms = (time.time() - start_t) * 1000.0
        await self.circuit_breaker.record_success()
        self.record_request_metrics(latency_ms, is_success=True)

        return {
            "success": True,
            "status": "SENT",
            "provider": self.provider_name,
            "provider_push_id": push_id,
            "device_count": len(device_tokens),
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
        }
