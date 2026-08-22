import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, Optional
from ...schemas.integrations import CircuitBreakerState

logger = logging.getLogger("toursafe.integrations.circuit_breaker")


class CircuitBreakerOpenException(Exception):
    def __init__(self, provider_name: str, cooldown_remaining_seconds: float):
        super().__init__(f"Circuit breaker for provider '{provider_name}' is OPEN. Cooldown remaining: {cooldown_remaining_seconds:.1f}s")
        self.provider_name = provider_name
        self.cooldown_remaining_seconds = cooldown_remaining_seconds


class CircuitBreaker:
    """
    Asynchronous, thread-safe circuit breaker for external providers.
    States:
    - CLOSED: Normal operation. Requests pass through.
    - OPEN: Provider failed threshold consecutive times. Requests fast-fail immediately.
    - HALF_OPEN: Cooldown expired. Testing single trial request to determine recovery.
    """

    def __init__(
        self,
        provider_name: str,
        failure_threshold: int = 5,
        recovery_cooldown_seconds: float = 30.0,
        half_open_success_threshold: int = 1,
    ):
        self.provider_name = provider_name
        self.failure_threshold = failure_threshold
        self.recovery_cooldown_seconds = recovery_cooldown_seconds
        self.half_open_success_threshold = half_open_success_threshold

        self._state = CircuitBreakerState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change: float = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitBreakerState:
        # Check if OPEN cooldown has elapsed to auto-transition to HALF_OPEN
        if self._state == CircuitBreakerState.OPEN and self._last_failure_time:
            now = datetime.now(timezone.utc).timestamp()
            if now - self._last_failure_time >= self.recovery_cooldown_seconds:
                return CircuitBreakerState.HALF_OPEN
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    async def before_execution(self) -> None:
        """Verify circuit status before executing call. Raises CircuitBreakerOpenException if OPEN."""
        current_state = self.state
        if current_state == CircuitBreakerState.OPEN:
            now = datetime.now(timezone.utc).timestamp()
            remaining = max(0.0, self.recovery_cooldown_seconds - (now - (self._last_failure_time or now)))
            logger.warning(
                "CircuitBreaker: Blocked request to %s (Circuit is OPEN, remaining cooldown: %.1fs)",
                self.provider_name,
                remaining,
            )
            raise CircuitBreakerOpenException(self.provider_name, remaining)

    async def record_success(self) -> None:
        """Record successful upstream execution."""
        async with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN or self.state == CircuitBreakerState.HALF_OPEN:
                self._consecutive_successes += 1
                if self._consecutive_successes >= self.half_open_success_threshold:
                    self._state = CircuitBreakerState.CLOSED
                    self._consecutive_failures = 0
                    self._consecutive_successes = 0
                    logger.info("CircuitBreaker for %s: RECOVERED and transitioned HALF_OPEN -> CLOSED", self.provider_name)
            else:
                self._consecutive_failures = 0

    async def record_failure(self, error: Optional[Exception] = None) -> None:
        """Record upstream failure."""
        async with self._lock:
            self._consecutive_failures += 1
            self._last_failure_time = datetime.now(timezone.utc).timestamp()
            self._consecutive_successes = 0

            if self._state == CircuitBreakerState.HALF_OPEN or self.state == CircuitBreakerState.HALF_OPEN:
                # Trial failed in HALF_OPEN -> reopen immediately
                self._state = CircuitBreakerState.OPEN
                logger.warning("CircuitBreaker for %s: Trial request failed. Transitioning HALF_OPEN -> OPEN", self.provider_name)
            elif self._consecutive_failures >= self.failure_threshold:
                self._state = CircuitBreakerState.OPEN
                logger.error(
                    "CircuitBreaker for %s: Failure threshold (%d) reached. Transitioning CLOSED -> OPEN for %.1fs. Error: %s",
                    self.provider_name,
                    self.failure_threshold,
                    self.recovery_cooldown_seconds,
                    str(error),
                )

    def reset(self) -> None:
        """Force reset circuit breaker to healthy CLOSED state."""
        self._state = CircuitBreakerState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_failure_time = None
