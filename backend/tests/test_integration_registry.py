import pytest
from app.schemas.integrations import IntegrationStatus, IntegrationType
from app.services.integrations.registry import IntegrationRegistry
from app.services.integrations.adapters import DevMapsAdapter, DevWeatherAdapter, SMSAdapter


@pytest.mark.asyncio
async def test_01_registry_initialization_and_defaults():
    registry = IntegrationRegistry()
    await registry.initialize_defaults()

    integrations = await registry.list_integrations()
    assert len(integrations) >= 10

    provider_names = [i.provider_name for i in integrations]
    assert "DEV_MAPS_PROVIDER" in provider_names
    assert "DEV_WEATHER_PROVIDER" in provider_names
    assert "DEV_SMS_ADAPTER" in provider_names
    assert "DEV_IDENTITY_PROVIDER" in provider_names
    assert "DEV_EMERGENCY_CAD_ADAPTER" in provider_names


@pytest.mark.asyncio
async def test_02_primary_and_fallback_adapter_resolution():
    registry = IntegrationRegistry()
    dev_maps = DevMapsAdapter()
    sms = SMSAdapter("DEV_SMS_ADAPTER")

    registry.register_adapter(dev_maps, is_primary=True)
    registry.register_adapter(sms, is_primary=True)

    primary_maps = registry.get_primary_adapter(IntegrationType.MAPS)
    assert primary_maps is not None
    assert primary_maps.provider_name == "DEV_MAPS_PROVIDER"

    active_adapter, fallback = registry.get_adapter_with_fallback(IntegrationType.MAPS)
    assert active_adapter.provider_name == "DEV_MAPS_PROVIDER"


@pytest.mark.asyncio
async def test_03_test_connection_probe():
    registry = IntegrationRegistry()
    await registry.initialize_defaults()

    res = await registry.test_connection("DEV_MAPS_PROVIDER", actor_id="TEST_ADMIN")
    assert res["success"] is True
    assert res["status"] == IntegrationStatus.ACTIVE.value
    assert res["latency_ms"] >= 0.0
    assert "circuit_state" in res


@pytest.mark.asyncio
async def test_04_configuration_update_and_audit():
    registry = IntegrationRegistry()
    await registry.initialize_defaults()

    updated_cfg = await registry.update_configuration(
        provider_name="DEV_WEATHER_PROVIDER",
        enabled=False,
        timeout_seconds=8.5,
        actor_id="TEST_ADMIN",
    )
    assert updated_cfg.enabled is False
    assert updated_cfg.timeout_seconds == 8.5

    # Health status should reflect disabled state
    adapter = registry.get_adapter("DEV_WEATHER_PROVIDER")
    health = adapter.get_health_status()
    assert health.status == IntegrationStatus.DISABLED

    # Re-enable
    await registry.update_configuration(
        provider_name="DEV_WEATHER_PROVIDER",
        enabled=True,
        actor_id="TEST_ADMIN",
    )
    assert adapter.get_health_status().status == IntegrationStatus.ACTIVE
