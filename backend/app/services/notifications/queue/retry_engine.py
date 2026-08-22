from dataclasses import dataclass
import logging
import random
from typing import Optional

from ....schemas.notification import DeliveryErrorCategory

logger = logging.getLogger("toursafe.notifications.queue.retry")


@dataclass
class RetryConfig:
    initial_delay_sec: float = 1.0
    max_delay_sec: float = 60.0
    backoff_multiplier: float = 2.0
    jitter_factor: float = 0.2
    max_attempts: int = 3


class RetryEngine:
    """
    Retry Engine for TourSafe Notification Infrastructure.
    Calculates exponential backoff with jitter and classifies error recoverability.
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()

    def should_retry(self, attempt_count: int, error_category: Optional[DeliveryErrorCategory]) -> bool:
        """
        Determine if an attempt should be retried based on attempt count and error classification.
        Permanent errors (invalid phone, malformed email, unregistered token) are NEVER retried.
        """
        if attempt_count >= self.config.max_attempts:
            return False

        if error_category in (
            DeliveryErrorCategory.PERMANENT,
            DeliveryErrorCategory.INVALID_RECIPIENT,
            DeliveryErrorCategory.AUTH_FAILURE,
        ):
            return False

        return True

    def calculate_backoff_delay(self, attempt_count: int) -> float:
        """
        Calculate backoff delay in seconds:
        delay = min(max_delay, initial_delay * (multiplier ** (attempt_count - 1))) ± jitter
        """
        if attempt_count <= 1:
            base = self.config.initial_delay_sec
        else:
            base = min(
                self.config.max_delay_sec,
                self.config.initial_delay_sec * (self.config.backoff_multiplier ** (attempt_count - 1)),
            )

        # Apply random jitter
        jitter = base * self.config.jitter_factor * (random.random() * 2 - 1)
        return max(0.1, base + jitter)


retry_engine = RetryEngine()
