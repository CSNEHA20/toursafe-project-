from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
import uuid

from ....schemas.notification import (
    DeliveryErrorCategory,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
)

logger = logging.getLogger("toursafe.notifications.providers.base")


@dataclass
class ProviderDeliveryResult:
    status: NotificationStatus
    provider_name: str
    provider_message_id: Optional[str] = None
    detail: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_category: Optional[DeliveryErrorCategory] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class NotificationProvider(ABC):
    """
    Abstract base class for all notification delivery providers.
    Provides uniform status checking, health diagnostics, delivery execution, and cancellation.
    """

    def __init__(self, name: str, channel: NotificationChannel):
        self.name = name
        self.channel = channel

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if real API credentials or connections are present in configuration."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform a live or static health check of the provider gateway."""
        pass

    @abstractmethod
    async def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        metadata: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        idempotency_key: Optional[str] = None,
    ) -> ProviderDeliveryResult:
        """
        Execute dispatch through the underlying channel.
        Must return a structured ProviderDeliveryResult.
        """
        pass

    async def get_status(self, provider_message_id: str) -> Optional[NotificationStatus]:
        """Poll or check delivery status if supported by provider."""
        return None

    async def cancel(self, provider_message_id: str) -> bool:
        """Cancel queued or scheduled message if supported."""
        return False
