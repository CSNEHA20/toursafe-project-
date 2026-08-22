import pytest
from app.services.copilot.tool_registry import copilot_tool_registry
from app.services.integrations.dead_letter import dead_letter_service
from app.schemas.integrations import IntegrationType


@pytest.mark.asyncio
async def test_01_copilot_integration_health_tool():
    res = await copilot_tool_registry.execute_tool(
        tool_name="get_integration_health",
        arguments={},
        user_context={"role": "admin", "user_id": "ADM_COPILOT"},
    )
    assert res["success"] is True
    assert len(res["data"]) >= 10
    assert res["source"] == "Integration Registry & Health Monitor"


@pytest.mark.asyncio
async def test_02_copilot_external_weather_query_tool():
    res = await copilot_tool_registry.execute_tool(
        tool_name="query_external_weather",
        arguments={"latitude": 15.4989, "longitude": 73.8278},
        user_context={"role": "dispatcher", "user_id": "DISP_01"},
    )
    assert res["success"] is True
    assert "temperature_celsius" in res["data"]
    assert "feels_like_celsius" in res["data"]


@pytest.mark.asyncio
async def test_03_copilot_external_geocoding_and_routing_tools():
    # Geocoding
    geo_res = await copilot_tool_registry.execute_tool(
        tool_name="query_external_geocoding",
        arguments={"address": "Baga Beach"},
        user_context={"role": "dispatcher", "user_id": "DISP_01"},
    )
    assert geo_res["success"] is True
    assert geo_res["data"]["latitude"] > 0

    # Routing
    route_res = await copilot_tool_registry.execute_tool(
        tool_name="query_external_routing",
        arguments={"origin_lon": 73.7554, "origin_lat": 15.5439, "dest_lon": 73.8278, "dest_lat": 15.4989},
        user_context={"role": "commander", "user_id": "COMM_01"},
    )
    assert route_res["success"] is True
    assert route_res["data"]["distance_meters"] > 0


@pytest.mark.asyncio
async def test_04_copilot_dead_letter_tools_and_write_authorization():
    # 1. Enqueue dummy DLQ
    rec = await dead_letter_service.enqueue(
        operation_name="copilot_test_failed_sms",
        integration_id="int_sms",
        provider_name="DEV_SMS_ADAPTER",
        integration_type=IntegrationType.SMS,
        idempotency_key="copilot_key_999",
        correlation_id="corr_copilot_01",
        attempt_count=3,
        max_attempts=3,
        error_code="TIMEOUT",
        error_message="Gateway timeout",
    )

    # 2. List dead letters via copilot tool
    list_res = await copilot_tool_registry.execute_tool(
        tool_name="list_integration_dead_letters",
        arguments={"resolved": False},
        user_context={"role": "admin", "user_id": "ADM_COPILOT"},
    )
    assert list_res["success"] is True
    assert any(r["record_id"] == rec.record_id for r in list_res["data"])

    # 3. Retry tool is marked with requires_preview=True
    tool_def = copilot_tool_registry.get_tool("retry_integration_dead_letter")
    assert tool_def.read_only is False
    assert tool_def.requires_preview is True

    # 4. Execute retry tool
    retry_res = await copilot_tool_registry.execute_tool(
        tool_name="retry_integration_dead_letter",
        arguments={"record_id": rec.record_id},
        user_context={"role": "admin", "user_id": "ADM_COPILOT"},
    )
    assert retry_res["success"] is True
    assert retry_res["data"]["status"] == "RETRY_QUEUED"
