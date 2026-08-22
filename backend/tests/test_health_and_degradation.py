"""
Unit and Integration Tests for Health Checks, Probes, Degradation Modes, and Priority Enforcement.
"""

import pytest
from fastapi import HTTPException
from app.core.reliability.degradation import (
    degradation_manager,
    SystemMode,
    ServicePriority,
    require_priority_allowance,
    ServicePriorityRegistry,
)
from app.core.reliability.db_resilience import check_db_health
from app.core.reliability.redis_resilience import check_resilient_redis_health


def test_01_priority_registry_classification():
    # Verify life-safety services are strictly marked CRITICAL
    assert ServicePriorityRegistry.SERVICES["sos_ingestion"][0] == ServicePriority.CRITICAL
    assert ServicePriorityRegistry.SERVICES["incident_lifecycle"][0] == ServicePriority.CRITICAL
    assert ServicePriorityRegistry.SERVICES["responder_dispatch"][0] == ServicePriority.CRITICAL
    assert ServicePriorityRegistry.SERVICES["telemetry_ingestion"][0] == ServicePriority.CRITICAL
    
    # Auxiliary services must NOT be marked CRITICAL
    assert ServicePriorityRegistry.SERVICES["ai_copilot"][0] == ServicePriority.NON_CRITICAL
    assert ServicePriorityRegistry.SERVICES["analytics_forecast"][0] == ServicePriority.NON_CRITICAL
    assert ServicePriorityRegistry.SERVICES["heatmap_generation"][0] == ServicePriority.NON_CRITICAL


def test_02_degradation_modes_and_load_shedding():
    # 1. FULL Mode: all services allowed
    degradation_manager.set_mode(SystemMode.FULL, "Normal operations")
    assert degradation_manager.is_service_allowed(ServicePriority.CRITICAL) is True
    assert degradation_manager.is_service_allowed(ServicePriority.HIGH) is True
    assert degradation_manager.is_service_allowed(ServicePriority.NORMAL) is True
    assert degradation_manager.is_service_allowed(ServicePriority.NON_CRITICAL) is True

    # 2. CRITICAL_ONLY Mode: only CRITICAL and HIGH allowed
    degradation_manager.set_mode(SystemMode.CRITICAL_ONLY, "Extreme CPU and DB load")
    assert degradation_manager.is_service_allowed(ServicePriority.CRITICAL) is True
    assert degradation_manager.is_service_allowed(ServicePriority.HIGH) is True
    assert degradation_manager.is_service_allowed(ServicePriority.NORMAL) is False
    assert degradation_manager.is_service_allowed(ServicePriority.NON_CRITICAL) is False

    # Verify requirement guard raises HTTP 503 for non-critical
    require_priority_allowance(ServicePriority.CRITICAL)  # Should pass without error

    with pytest.raises(HTTPException) as exc_info:
        require_priority_allowance(ServicePriority.NON_CRITICAL, subsystem_name="ai_copilot")
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error"] == "SERVICE_DEGRADED_LOAD_SHEDDING"

    # Reset back to FULL
    degradation_manager.set_mode(SystemMode.FULL, "Test teardown reset")


@pytest.mark.asyncio
async def test_03_db_and_redis_health_checks():
    db_health = await check_db_health()
    assert db_health["status"] in ["HEALTHY", "DEGRADED", "UNAVAILABLE"]
    if db_health["status"] == "HEALTHY":
        assert db_health["latency_ms"] is not None

    redis_health = await check_resilient_redis_health()
    assert redis_health["status"] in ["HEALTHY", "DEGRADED", "DISABLED", "UNAVAILABLE"]
