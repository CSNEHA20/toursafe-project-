from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from ....schemas.integrations import (
    CircuitBreakerState,
    IntegrationConfig,
    IntegrationHealthStatus,
    IntegrationStatus,
    IntegrationType,
)
from ..circuit_breaker import CircuitBreaker
from ..security import security_manager

logger = logging.getLogger("toursafe.integrations.adapters.base")


class IntegrationAdapter(ABC):
    """
    Abstract Base Class for all External Integration Adapters.
    Encapsulates provider SDK details, API credentials, endpoints, health checks,
    circuit breaking, timeouts, and error normalization.
    """

    def __init__(
        self,
        provider_name: str,
        integration_type: IntegrationType,
        is_real_provider: bool = False,
        config: Optional[IntegrationConfig] = None,
    ):
        self.provider_name = provider_name
        self.integration_type = integration_type
        self.is_real_provider = is_real_provider
        self.config = config or IntegrationConfig(
            provider_name=provider_name,
            integration_type=integration_type,
        )
        self.circuit_breaker = CircuitBreaker(
            provider_name=provider_name,
            failure_threshold=self.config.circuit_failure_threshold,
            recovery_cooldown_seconds=self.config.circuit_recovery_cooldown_seconds,
        )
        self._last_success_time: Optional[str] = None
        self._last_failure_time: Optional[str] = None
        self._last_latency_ms: float = 0.0

    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """List of capabilities supported by this adapter (e.g. geocoding, routing, sms_send)."""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize connections, pools, or validation."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Cleanly shutdown adapter resources."""
        pass

    @abstractmethod
    async def execute_health_check(self) -> IntegrationHealthStatus:
        """Execute a connectivity and health probe to the upstream provider."""
        pass

    def get_health_status(self) -> IntegrationHealthStatus:
        """Get current cached health state including circuit breaker condition."""
        cb_state = self.circuit_breaker.state
        status = IntegrationStatus.ACTIVE
        if not self.config.enabled:
            status = IntegrationStatus.DISABLED
        elif cb_state == CircuitBreakerState.OPEN:
            status = IntegrationStatus.FAILED
        elif cb_state == CircuitBreakerState.HALF_OPEN:
            status = IntegrationStatus.DEGRADED

        return IntegrationHealthStatus(
            status=status,
            is_healthy=(status == IntegrationStatus.ACTIVE),
            latency_ms=self._last_latency_ms,
            last_successful_request=self._last_success_time,
            last_failure=self._last_failure_time,
            consecutive_failures=self.circuit_breaker.consecutive_failures,
            circuit_state=cb_state,
            detail=f"{self.provider_name} ({'Real' if self.is_real_provider else 'Simulated/Dev'}) - Circuit {cb_state.value}",
            checked_at=datetime.now(timezone.utc).isoformat(),
        )

    def record_request_metrics(self, latency_ms: float, is_success: bool) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._last_latency_ms = round(latency_ms, 2)
        if is_success:
            self._last_success_time = now
        else:
            self._last_failure_time = now
