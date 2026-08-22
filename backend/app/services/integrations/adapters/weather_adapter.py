from abc import abstractmethod
from datetime import datetime, timezone, timedelta
import logging
import time
from typing import Any, Dict, List, Optional

from ....schemas.integrations import (
    IntegrationConfig,
    IntegrationHealthStatus,
    IntegrationStatus,
    IntegrationType,
    SevereWeatherAlert,
    WeatherCondition,
)
from .base import IntegrationAdapter

logger = logging.getLogger("toursafe.integrations.adapters.weather")


class WeatherAdapter(IntegrationAdapter):
    """
    Normalized Weather Intelligence Adapter Interface.
    """

    def __init__(
        self,
        provider_name: str = "DEV_WEATHER_ADAPTER",
        is_real_provider: bool = False,
        config: Optional[IntegrationConfig] = None,
    ):
        super().__init__(
            provider_name=provider_name,
            integration_type=IntegrationType.WEATHER,
            is_real_provider=is_real_provider,
            config=config or IntegrationConfig(
                provider_name=provider_name,
                integration_type=IntegrationType.WEATHER,
                allowlist_domains=["api.open-meteo.com", "api.weatherapi.com"],
            ),
        )

    @property
    def capabilities(self) -> List[str]:
        return ["current_weather", "hourly_forecast", "severe_alerts", "marine_conditions", "air_quality"]

    @abstractmethod
    async def get_current_weather(self, latitude: float, longitude: float) -> WeatherCondition:
        pass

    @abstractmethod
    async def get_severe_alerts(self, latitude: float, longitude: float) -> List[SevereWeatherAlert]:
        pass


class DevWeatherAdapter(WeatherAdapter):
    """
    Deterministic Development / Testing Weather Adapter.
    Generates realistic coastal & tropical weather states for simulation without external API calls.
    """

    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(provider_name="DEV_WEATHER_PROVIDER", is_real_provider=False, config=config)

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def execute_health_check(self) -> IntegrationHealthStatus:
        status = self.get_health_status()
        status.latency_ms = 3.5
        status.is_healthy = True
        status.detail = "Dev Weather provider operational"
        return status

    async def get_current_weather(self, latitude: float, longitude: float) -> WeatherCondition:
        start_t = time.time()
        await self.circuit_breaker.before_execution()

        # Deterministic variation based on latitude
        is_monsoon = (int(latitude * 100) % 7 == 0)
        temp = 29.5 if not is_monsoon else 24.0
        precip = 0.0 if not is_monsoon else 35.0
        wind = 14.0 if not is_monsoon else 48.0
        visibility = 10.0 if not is_monsoon else 2.5

        latency_ms = (time.time() - start_t) * 1000.0
        await self.circuit_breaker.record_success()
        self.record_request_metrics(latency_ms, is_success=True)

        return WeatherCondition(
            temperature_celsius=temp,
            feels_like_celsius=temp + 3.0,
            humidity_percent=78.0,
            wind_speed_kmh=wind,
            wind_direction="WSW",
            precipitation_mm=precip,
            visibility_km=visibility,
            uv_index=6.0,
            condition_text="Heavy Monsoon Rain & High Wind" if is_monsoon else "Partly Cloudy Coastal Breezes",
            condition_code="MONSOON_STORM" if is_monsoon else "PARTLY_CLOUDY",
            is_hazardous=is_monsoon,
            safety_bulletin="Severe thunderstorm warning active for coastal marine sector." if is_monsoon else None,
            observed_at=datetime.now(timezone.utc).isoformat(),
            provider=self.provider_name,
            attribution="TourSafe Dev Weather Engine (Simulated)",
        )

    async def get_severe_alerts(self, latitude: float, longitude: float) -> List[SevereWeatherAlert]:
        start_t = time.time()
        await self.circuit_breaker.before_execution()

        latency_ms = (time.time() - start_t) * 1000.0
        await self.circuit_breaker.record_success()
        self.record_request_metrics(latency_ms, is_success=True)

        # Check if region has active storm
        now = datetime.now(timezone.utc)
        if int(latitude * 100) % 7 == 0:
            return [
                SevereWeatherAlert(
                    alert_id=f"wx_alert_{int(now.timestamp())}",
                    severity="SEVERE",
                    headline="High Surf & Rip Current Advisory",
                    description="Strong onshore monsoon squalls generating rough surf and dangerous rip currents along North Goa beaches.",
                    effective_from=now.isoformat(),
                    expires_at=(now + timedelta(hours=6)).isoformat(),
                    affected_area="Goa Coastal Belt",
                    provider=self.provider_name,
                )
            ]
        return []
