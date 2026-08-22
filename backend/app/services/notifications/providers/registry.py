import logging
from typing import Any, Dict, List, Optional

from ....schemas.notification import (
    NotificationChannel,
    ProviderHealthResponse,
)
from .base import NotificationProvider
from .email_provider import EmailNotificationProvider
from .in_app_provider import InAppNotificationProvider
from .push_provider import PushNotificationProvider
from .realtime_provider import RealtimeNotificationProvider
from .sms_provider import SMSNotificationProvider
from .voice_provider import VoiceCallNotificationProvider

logger = logging.getLogger("toursafe.notifications.providers.registry")


class ProviderRegistry:
    """
    Central provider registry managing channel adapters, health checking,
    and runtime dispatch routing.
    """

    def __init__(self):
        self._providers: Dict[NotificationChannel, NotificationProvider] = {
            NotificationChannel.IN_APP: InAppNotificationProvider(),
            NotificationChannel.REALTIME: RealtimeNotificationProvider(),
            NotificationChannel.PUSH: PushNotificationProvider(),
            NotificationChannel.SMS: SMSNotificationProvider(),
            NotificationChannel.EMAIL: EmailNotificationProvider(),
            NotificationChannel.VOICE: VoiceCallNotificationProvider(),
        }

    def get_provider(self, channel: NotificationChannel) -> Optional[NotificationProvider]:
        return self._providers.get(channel)

    def register_provider(self, channel: NotificationChannel, provider: NotificationProvider):
        logger.info("Registering custom provider '%s' for channel %s", provider.name, channel.value)
        self._providers[channel] = provider

    async def get_all_health_statuses(self) -> List[ProviderHealthResponse]:
        results: List[ProviderHealthResponse] = []
        for channel, prov in self._providers.items():
            health = await prov.health_check()
            results.append(
                ProviderHealthResponse(
                    provider_name=prov.name,
                    channel=channel,
                    configured=prov.is_configured(),
                    status=health.get("status", "UNKNOWN"),
                    detail=health.get("detail", ""),
                )
            )
        return results


provider_registry = ProviderRegistry()
