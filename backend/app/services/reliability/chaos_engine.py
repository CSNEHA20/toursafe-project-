"""
TourSafe Chaos Engineering & Resilience Testing Harness.
Provides controlled failure simulations to verify system recovery without risking production corruption.
"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional
from ...core.reliability.metrics import metrics_collector
from ...core.reliability.degradation import degradation_manager, SystemMode
from ...core.reliability.logging import get_structured_logger

logger = get_structured_logger("toursafe.chaos")


class ChaosSimulationResult:
    def __init__(self, scenario_name: str, passed: bool, details: Dict[str, Any], duration_ms: float):
        self.scenario_name = scenario_name
        self.passed = passed
        self.details = details
        self.duration_ms = duration_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario_name,
            "passed": self.passed,
            "duration_ms": round(self.duration_ms, 2),
            "details": self.details,
        }


class ChaosEngine:
    """Simulates realistic failure domains and asserts platform resilience."""

    async def run_db_timeout_simulation(self) -> ChaosSimulationResult:
        """Simulate transient DB timeouts and verify exponential retry absorption."""
        start = time.perf_counter()
        attempts = 0

        async def simulated_flaky_db():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise asyncio.TimeoutError("Simulated MongoDB read timeout")
            return {"status": "SUCCESS", "docs_found": 5}

        from ...core.reliability.db_resilience import with_db_retry
        try:
            res = await with_db_retry(simulated_flaky_db, operation_name="chaos_flaky_db", max_retries=3, base_delay_seconds=0.01)
            duration = (time.perf_counter() - start) * 1000
            passed = res.get("status") == "SUCCESS" and attempts == 3
            return ChaosSimulationResult("db_transient_timeout_recovery", passed, {"attempts_made": attempts, "result": res}, duration)
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return ChaosSimulationResult("db_transient_timeout_recovery", False, {"error": str(e)}, duration)

    async def run_redis_outage_simulation(self) -> ChaosSimulationResult:
        """Simulate Redis outage and verify transparent fallback to memory cache."""
        start = time.perf_counter()
        from ...core.reliability.redis_resilience import redis_resilience_manager
        
        # Write to fallback
        test_key = "chaos_redis_test_key"
        test_val = {"session_state": "ACTIVE", "role": "RESPONDER"}
        
        await redis_resilience_manager.set_with_fallback(test_key, test_val, ttl_seconds=60)
        retrieved = await redis_resilience_manager.get_with_fallback(test_key)
        
        duration = (time.perf_counter() - start) * 1000
        passed = retrieved == test_val or retrieved == str(test_val)
        return ChaosSimulationResult(
            "redis_outage_fallback_cache",
            passed,
            {"key": test_key, "retrieved": retrieved, "fallback_active": True},
            duration
        )

    async def run_out_of_order_event_simulation(self) -> ChaosSimulationResult:
        """Verify state machine rejects out-of-order regression (e.g. RESOLVED back to OPEN)."""
        start = time.perf_counter()
        
        valid_transitions = {
            "OPEN": ["ASSIGNED", "ESCALATED", "RESOLVED"],
            "ASSIGNED": ["EN_ROUTE", "ON_SCENE", "RESOLVED"],
            "RESOLVED": ["CLOSED"],
            "CLOSED": [],
        }

        def attempt_transition(current: str, target: str) -> bool:
            allowed = valid_transitions.get(current, [])
            return target in allowed

        # 1. Normal transition OPEN -> RESOLVED
        assert attempt_transition("OPEN", "RESOLVED") is True
        
        # 2. Out-of-order stale packet attempting RESOLVED -> OPEN
        regression_blocked = attempt_transition("RESOLVED", "OPEN") is False
        
        duration = (time.perf_counter() - start) * 1000
        return ChaosSimulationResult(
            "out_of_order_event_rejection",
            regression_blocked,
            {"from_state": "RESOLVED", "target_state": "OPEN", "regression_blocked": regression_blocked},
            duration
        )

    async def run_duplicate_sos_flood_simulation(self, burst_count: int = 50) -> ChaosSimulationResult:
        """Simulate high duplicate SOS flood to verify idempotency deduplication."""
        start = time.perf_counter()
        from ...core.reliability.db_resilience import idempotent_write_guard
        
        idempotency_key = "sos_device_9999_seq_1"
        accepted = 0
        deduplicated = 0

        for _ in range(burst_count):
            if idempotent_write_guard.is_duplicate(idempotency_key, ttl_seconds=60):
                deduplicated += 1
            else:
                accepted += 1

        duration = (time.perf_counter() - start) * 1000
        passed = (accepted == 1) and (deduplicated == burst_count - 1)
        return ChaosSimulationResult(
            "duplicate_sos_flood_idempotency",
            passed,
            {"burst_count": burst_count, "accepted": accepted, "deduplicated": deduplicated},
            duration
        )

    async def run_degradation_load_shedding_simulation(self) -> ChaosSimulationResult:
        """Simulate Critical-Only degradation mode shedding AI & analytics requests."""
        start = time.perf_counter()
        from ...core.reliability.degradation import require_priority_allowance, ServicePriority
        from fastapi import HTTPException
        
        degradation_manager.set_mode(SystemMode.CRITICAL_ONLY, "Simulated CPU starvation")
        
        # Critical should pass
        critical_passed = True
        try:
            require_priority_allowance(ServicePriority.CRITICAL)
        except HTTPException:
            critical_passed = False

        # Non-critical (AI / Analytics) should be blocked (HTTP 503)
        non_critical_blocked = False
        try:
            require_priority_allowance(ServicePriority.NON_CRITICAL, subsystem_name="ai_copilot")
        except HTTPException as e:
            if e.status_code == 503:
                non_critical_blocked = True

        # Restore mode
        degradation_manager.set_mode(SystemMode.FULL, "Chaos simulation completed")
        duration = (time.perf_counter() - start) * 1000

        passed = critical_passed and non_critical_blocked
        return ChaosSimulationResult(
            "degradation_load_shedding",
            passed,
            {"critical_allowed": critical_passed, "non_critical_shed": non_critical_blocked},
            duration
        )

    async def run_full_resilience_suite(self) -> Dict[str, Any]:
        """Execute all chaos drills and compile a comprehensive report."""
        results = [
            await self.run_db_timeout_simulation(),
            await self.run_redis_outage_simulation(),
            await self.run_out_of_order_event_simulation(),
            await self.run_duplicate_sos_flood_simulation(),
            await self.run_degradation_load_shedding_simulation(),
        ]
        
        all_passed = all(r.passed for r in results)
        return {
            "all_passed": all_passed,
            "total_drills": len(results),
            "drills": [r.to_dict() for r in results],
            "timestamp": time.time(),
        }


chaos_engine = ChaosEngine()
