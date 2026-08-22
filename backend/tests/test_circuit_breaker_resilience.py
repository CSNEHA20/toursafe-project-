import asyncio
import pytest
from app.schemas.integrations import CircuitBreakerState, IntegrationType
from app.services.integrations.circuit_breaker import CircuitBreaker, CircuitBreakerOpenException
from app.services.integrations.idempotency import IdempotencyManager
from app.services.integrations.retry_engine import RetryEngine, RetryExhaustedException
from app.services.integrations.registry import IntegrationRegistry
from app.services.integrations.adapters import DevMapsAdapter, OpenStreetMapAdapter


@pytest.mark.asyncio
async def test_01_circuit_breaker_state_transitions():
    # 3 failure threshold, 0.2s cooldown
    cb = CircuitBreaker("TEST_PROVIDER", failure_threshold=3, recovery_cooldown_seconds=0.2)
    assert cb.state == CircuitBreakerState.CLOSED

    # 1st failure
    await cb.record_failure(RuntimeError("Transient error 1"))
    assert cb.state == CircuitBreakerState.CLOSED

    # 2nd failure
    await cb.record_failure(RuntimeError("Transient error 2"))
    assert cb.state == CircuitBreakerState.CLOSED

    # 3rd failure -> trips OPEN
    await cb.record_failure(RuntimeError("Threshold breach error"))
    assert cb.state == CircuitBreakerState.OPEN

    # Subsequent call fast-fails immediately
    with pytest.raises(CircuitBreakerOpenException) as exc_info:
        await cb.before_execution()
    assert "is OPEN" in str(exc_info.value)

    # Wait for cooldown to expire
    await asyncio.sleep(0.25)
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # Record success on trial request -> recovers to CLOSED
    await cb.record_success()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.consecutive_failures == 0


@pytest.mark.asyncio
async def test_02_retry_engine_bounded_backoff():
    attempts_made = 0

    async def flaky_operation():
        nonlocal attempts_made
        attempts_made += 1
        if attempts_made < 3:
            raise ConnectionResetError("Temporary network disconnect")
        return {"status": "SUCCESS", "attempts": attempts_made}

    result = await RetryEngine.execute_with_retry(
        coro_fn=flaky_operation,
        operation_name="flaky_endpoint",
        max_attempts=3,
        base_delay_seconds=0.05,
    )
    assert result["status"] == "SUCCESS"
    assert attempts_made == 3


@pytest.mark.asyncio
async def test_03_retry_engine_exhaustion():
    async def always_failing():
        raise TimeoutError("Provider unreachable timeout")

    with pytest.raises(RetryExhaustedException) as exc:
        await RetryEngine.execute_with_retry(
            coro_fn=always_failing,
            operation_name="permanent_failure",
            max_attempts=3,
            base_delay_seconds=0.01,
        )
    assert exc.value.attempts == 3


@pytest.mark.asyncio
async def test_04_idempotency_manager_duplicate_deduplication():
    mgr = IdempotencyManager(default_ttl_seconds=60)
    key = "req_12345"
    payload = {"tourist_id": "T-100", "incident_id": "INC-001"}

    is_dup1, res1 = await mgr.check_or_record(key, payload)
    assert is_dup1 is False
    assert res1 is None

    # Store completed response
    await mgr.store_response(key, {"external_id": "EXT-999", "status": "CONFIRMED"})

    # Replay same request with same key
    is_dup2, res2 = await mgr.check_or_record(key, payload)
    assert is_dup2 is True
    assert res2 == {"external_id": "EXT-999", "status": "CONFIRMED"}


@pytest.mark.asyncio
async def test_05_fallback_routing_when_primary_circuit_open():
    registry = IntegrationRegistry()
    primary_maps = DevMapsAdapter()
    fallback_maps = OpenStreetMapAdapter()

    registry.register_adapter(primary_maps, is_primary=True)
    registry.register_adapter(fallback_maps, is_primary=False)

    # Initially primary is active
    active, _ = registry.get_adapter_with_fallback(IntegrationType.MAPS)
    assert active.provider_name == primary_maps.provider_name

    # Trip primary circuit breaker to OPEN
    for _ in range(primary_maps.config.circuit_failure_threshold):
        await primary_maps.circuit_breaker.record_failure(RuntimeError("Forced failure"))

    assert primary_maps.circuit_breaker.state == CircuitBreakerState.OPEN

    # Now get_adapter_with_fallback should automatically route to secondary/fallback
    active_now, old_primary = registry.get_adapter_with_fallback(IntegrationType.MAPS)
    assert active_now.provider_name == fallback_maps.provider_name
    assert old_primary.provider_name == primary_maps.provider_name
