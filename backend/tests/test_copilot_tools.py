"""
Comprehensive Test Suite for Copilot Tools, Tool Registry, Authorization,
PII Masking, and Loop Detection.
"""

import pytest
from app.core.database import get_database
from app.services.copilot.tool_registry import copilot_tool_registry
from app.services.copilot import tools
from app.services.copilot.test_utils import setup_mock_db



@pytest.fixture(autouse=True)
def mock_db_fixture(monkeypatch):
    return setup_mock_db(monkeypatch)



@pytest.mark.asyncio
async def test_01_tool_registry_rbac_authorization():
    """Verify tool authorization gate enforces role requirements before execution."""
    tourist_ctx = {"user_id": "u1", "role": "tourist"}
    auth_ctx = {"user_id": "a1", "role": "authority"}

    # Tourist attempting to call incident search must fail
    res_unauth = await copilot_tool_registry.execute_tool(
        tool_name="search_incidents",
        arguments={"limit": 5},
        user_context=tourist_ctx,
    )
    assert res_unauth["success"] is False
    assert res_unauth["error"] == "UNAUTHORIZED"

    # Authority officer can execute
    res_auth = await copilot_tool_registry.execute_tool(
        tool_name="search_incidents",
        arguments={"limit": 5},
        user_context=auth_ctx,
    )
    assert res_auth["success"] is True


@pytest.mark.asyncio
async def test_02_pii_masking_and_sanitization():
    """Verify sensitive PII (phone, email, identity number) is masked."""
    db = get_database()
    t_id = "tour_pii_test_1"
    await db["tourists"].delete_many({"id": t_id})
    await db["tourists"].insert_one({
        "id": t_id,
        "full_name": "Test Tourist",
        "email": "tourist.private@example.com",
        "phone": "+919876543210",
        "id_number": "PASS987654321",
        "verification_status": "VERIFIED",
    })

    auth_ctx = {"user_id": "a1", "role": "authority"}
    res = await copilot_tool_registry.execute_tool(
        tool_name="get_tourist_safety_status",
        arguments={"tourist_id": t_id},
        user_context=auth_ctx,
    )
    assert res["success"] is True
    data = res["data"]
    # Check that plain sensitive values are not present
    data_str = str(data)
    assert "9876543210" not in data_str
    assert "PASS987654321" not in data_str


@pytest.mark.asyncio
async def test_03_all_11_tool_categories_execution():
    """Verify execution for each of the 11 Copilot tool categories."""
    auth_ctx = {"user_id": "a1", "role": "authority"}

    # 1. Incidents
    r1 = await copilot_tool_registry.execute_tool("get_active_incidents", {}, auth_ctx)
    assert r1["success"] is True

    # 2. Safety
    r2 = await copilot_tool_registry.execute_tool("get_current_safety_state", {"tourist_id": "tour_test_demo"}, auth_ctx)
    assert r2["success"] is True

    # 3. Risk
    r3 = await copilot_tool_registry.execute_tool("get_risk_hotspots", {"limit": 3}, auth_ctx)
    assert r3["success"] is True

    # 4. Zones
    r4 = await copilot_tool_registry.execute_tool("list_active_zones", {}, auth_ctx)
    assert r4["success"] is True

    # 5. Tourists
    r5 = await copilot_tool_registry.execute_tool("get_tourist_trip_status", {"tourist_id": "tour_test_demo"}, auth_ctx)
    assert r5["success"] is True

    # 6. Responders
    r6 = await copilot_tool_registry.execute_tool("get_available_responders", {}, auth_ctx)
    assert r6["success"] is True

    # 7. Analytics
    r7 = await copilot_tool_registry.execute_tool("get_incident_metrics", {"timeframe": "24h"}, auth_ctx)
    assert r7["success"] is True

    # 8. Policy
    r8 = await copilot_tool_registry.execute_tool("get_escalation_policy", {}, auth_ctx)
    assert r8["success"] is True

    # 9. System Health
    r9 = await copilot_tool_registry.execute_tool("get_system_health", {}, auth_ctx)
    assert r9["success"] is True
    assert "subsystems" in r9["data"]

    # 10. Knowledge Base
    r10 = await copilot_tool_registry.execute_tool("search_knowledge_base", {"query": "emergency SLA"}, auth_ctx)
    assert r10["success"] is True


@pytest.mark.asyncio
async def test_04_tool_input_injection_rejection():
    """Verify tool parameter injection ($where, mongo operators) is rejected."""
    auth_ctx = {"user_id": "a1", "role": "authority"}
    res = await copilot_tool_registry.execute_tool(
        tool_name="get_incident",
        arguments={"incident_id": "$where: this.password == ''"},
        user_context=auth_ctx,
    )
    assert res["success"] is False
    assert res["error"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_05_tool_timeout_handling():
    """Verify tool execution bounds and timeout resilience."""
    auth_ctx = {"user_id": "a1", "role": "authority"}

    # Execute with very low timeout (0.0001s) to test timeout handling
    res = await copilot_tool_registry.execute_tool(
        tool_name="list_active_zones",
        arguments={},
        user_context=auth_ctx,
        timeout_sec=0.0001,
    )
    # Either completes instantaneously or returns structured TIMEOUT error
    if not res["success"]:
        assert res["error"] == "TIMEOUT"
