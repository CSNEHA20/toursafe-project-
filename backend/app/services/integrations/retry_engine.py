import asyncio
import logging
import random
from typing import Any, Callable, Coroutine, List, Optional, Set, Type

logger = logging.getLogger("toursafe.integrations.retry")


class RetryExhaustedException(Exception):
    def __init__(self, operation_name: str, attempts: int, last_error: Exception):
        super().__init__(f"Retry policy exhausted for '{operation_name}' after {attempts} attempts. Last error: {last_error}")
        self.operation_name = operation_name
        self.attempts = attempts
        self.last_error = last_error


class RetryEngine:
    """
    Bounded exponential backoff retry executor with full jitter.
    Guarantees non-infinite retries and safe backoff.
    """

    @staticmethod
    async def execute_with_retry(
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
        operation_name: str,
        max_attempts: int = 3,
        base_delay_seconds: float = 0.5,
        max_delay_seconds: float = 10.0,
        backoff_multiplier: float = 2.0,
        retryable_exceptions: Optional[List[Type[Exception]]] = None,
        on_retry_callback: Optional[Callable[[int, Exception, float], None]] = None,
    ) -> Any:
        attempts = 0
        last_error: Optional[Exception] = None

        while attempts < max_attempts:
            attempts += 1
            try:
                return await coro_fn()
            except Exception as e:
                last_error = e
                # If specific retryable exceptions are given and error is not in list, fail immediately
                if retryable_exceptions:
                    if not any(isinstance(e, exc_cls) for exc_cls in retryable_exceptions):
                        logger.warning(
                            "RetryEngine: Non-retryable exception %s on attempt %d/%d for '%s'",
                            type(e).__name__,
                            attempts,
                            max_attempts,
                            operation_name,
                        )
                        raise e

                if attempts >= max_attempts:
                    logger.error(
                        "RetryEngine: Max attempts (%d) reached for '%s'. Raising RetryExhaustedException.",
                        max_attempts,
                        operation_name,
                    )
                    break

                # Calculate exponential delay with full jitter
                exp_delay = base_delay_seconds * (backoff_multiplier ** (attempts - 1))
                capped_delay = min(max_delay_seconds, exp_delay)
                actual_delay = random.uniform(0.5 * capped_delay, capped_delay)

                logger.info(
                    "RetryEngine: Attempt %d/%d failed for '%s' (%s: %s). Backing off for %.2fs...",
                    attempts,
                    max_attempts,
                    operation_name,
                    type(e).__name__,
                    str(e),
                    actual_delay,
                )

                if on_retry_callback:
                    try:
                        on_retry_callback(attempts, e, actual_delay)
                    except Exception:
                        pass

                await asyncio.sleep(actual_delay)

        raise RetryExhaustedException(operation_name, attempts, last_error or RuntimeError("Unknown retry failure"))
