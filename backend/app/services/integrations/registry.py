from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Type
import uuid

from ...core.database import get_database
from ...schemas.integrations import (
    CircuitBreakerState,
    IntegrationConfig,
    IntegrationHealthStatus,
    IntegrationRegistration,
    IntegrationStatus,
    IntegrationType,
)
from .adapters import (
    DocumentAdapter,
    EmailAdapter,
    EmergencyServiceAdapter,
    GoogleMapsAdapter,
    GovernmentAuthorityAdapter,
    IdentityProviderAdapter,
    IntegrationAdapter,
    MapboxAdapter,
    MapsAdapter,
    DevMapsAdapter,
    OpenStreetMapAdapter,
    PushAdapter,
    SMSAdapter,
    TourismDataAdapter,
    TranslationAdapter,
    VoiceAdapter,
    WeatherAdapter,
    DevWeatherAdapter,
)
from .audit import integration_audit_service
from .security import security_manager

logger = logging.getLogger("toursafe.integrations.registry")


class IntegrationRegistry:
    """
    Central Integration Registry and Fallback Router for TourSafe.
    Manages adapters, primary/fallback routing, circuit breaking, health aggregation,
    and sanitized configuration management.
    """

    def __init__(self):
        self._adapters: Dict[str, IntegrationAdapter] = {}  # provider_name -> adapter
        self._type_primary: Dict[IntegrationType, str] = {}  # type -> primary provider_name
        self._type_fallbacks: Dict[IntegrationType, List[str]] = {}  # type -> list of fallback provider_names
        self._initialized: bool = False

    def register_adapter(
        self,
        adapter: IntegrationAdapter,
        is_primary: bool = False,
    ) -> None:
        name = adapter.provider_name
        itype = adapter.integration_type
        self._adapters[name] = adapter

        if is_primary or itype not in self._type_primary:
            self._type_primary[itype] = name

        if itype not in self._type_fallbacks:
            self._type_fallbacks[itype] = []
        if name not in self._type_fallbacks[itype] and name != self._type_primary[itype]:
            self._type_fallbacks[itype].append(name)

        logger.info(
            "IntegrationRegistry: Registered '%s' (type=%s, is_primary=%s, capabilities=%s)",
            name,
            itype.value,
            is_primary,
            adapter.capabilities,
        )

    def get_adapter(self, provider_name: str) -> Optional[IntegrationAdapter]:
        return self._adapters.get(provider_name)

    def get_primary_adapter(self, integration_type: IntegrationType) -> Optional[IntegrationAdapter]:
        primary_name = self._type_primary.get(integration_type)
        if primary_name and primary_name in self._adapters:
            return self._adapters[primary_name]
        return None

    def get_adapter_with_fallback(self, integration_type: IntegrationType) -> Tuple[IntegrationAdapter, Optional[IntegrationAdapter]]:
        """
        Returns (active_adapter, fallback_adapter).
        If primary circuit breaker is OPEN or disabled, selects fallback adapter.
        """
        primary = self.get_primary_adapter(integration_type)
        fallbacks = self._type_fallbacks.get(integration_type, [])
        secondary = self._adapters.get(fallbacks[0]) if fallbacks else None

        if primary:
            # Check if primary is disabled or circuit is open
            if not primary.config.enabled or primary.circuit_breaker.state == CircuitBreakerState.OPEN:
                if secondary and secondary.config.enabled and secondary.circuit_breaker.state != CircuitBreakerState.OPEN:
                    logger.warning(
                        "IntegrationRegistry: Primary '%s' is degraded/open. Routing to fallback '%s'",
                        primary.provider_name,
                        secondary.provider_name,
                    )
                    return secondary, primary
            return primary, secondary

        if secondary:
            return secondary, None

        raise RuntimeError(f"No active adapter registered for integration type: {integration_type.value}")

    async def list_integrations(self) -> List[IntegrationRegistration]:
        results = []
        for name, adapter in self._adapters.items():
            health = adapter.get_health_status()
            reg = IntegrationRegistration(
                integration_id=f"int_{name.lower()}",
                provider_name=name,
                integration_type=adapter.integration_type,
                status=health.status,
                environment=adapter.config.environment,
                is_real_provider=adapter.is_real_provider,
                capabilities=adapter.capabilities,
                configuration=adapter.config,
                health=health,
            )
            results.append(reg)
        return results

    async def test_connection(self, provider_name: str, actor_id: str = "SYSTEM_ADMIN") -> Dict[str, Any]:
        adapter = self.get_adapter(provider_name)
        if not adapter:
            raise KeyError(f"Integration provider '{provider_name}' not found")

        start_t = time.time()
        try:
            health = await adapter.execute_health_check()
            latency_ms = (time.time() - start_t) * 1000.0

            await integration_audit_service.log_action(
                action="TEST_CONNECTION",
                actor_id=actor_id,
                actor_role="ADMIN",
                integration_id=f"int_{provider_name.lower()}",
                provider_name=provider_name,
                integration_type=adapter.integration_type,
                status="SUCCESS" if health.is_healthy else "DEGRADED",
                latency_ms=latency_ms,
                details={"detail": health.detail, "circuit_state": health.circuit_state.value},
            )

            return {
                "success": health.is_healthy,
                "provider_name": provider_name,
                "status": health.status.value,
                "latency_ms": round(latency_ms, 2),
                "detail": health.detail,
                "circuit_state": health.circuit_state.value,
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            latency_ms = (time.time() - start_t) * 1000.0
            await integration_audit_service.log_action(
                action="TEST_CONNECTION",
                actor_id=actor_id,
                actor_role="ADMIN",
                integration_id=f"int_{provider_name.lower()}",
                provider_name=provider_name,
                integration_type=adapter.integration_type,
                status="FAILED",
                latency_ms=latency_ms,
                details={"error": str(e)},
            )
            return {
                "success": False,
                "provider_name": provider_name,
                "status": IntegrationStatus.FAILED.value,
                "latency_ms": round(latency_ms, 2),
                "detail": f"Health check failed: {str(e)}",
                "circuit_state": adapter.circuit_breaker.state.value,
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }

    async def update_configuration(
        self,
        provider_name: str,
        enabled: Optional[bool] = None,
        is_primary: Optional[bool] = None,
        fallback_provider: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        actor_id: str = "SYSTEM_ADMIN",
    ) -> IntegrationConfig:
        adapter = self.get_adapter(provider_name)
        if not adapter:
            raise KeyError(f"Integration provider '{provider_name}' not found")

        changes = {}
        if enabled is not None:
            adapter.config.enabled = enabled
            changes["enabled"] = enabled
        if timeout_seconds is not None:
            adapter.config.timeout_seconds = timeout_seconds
            changes["timeout_seconds"] = timeout_seconds
        if fallback_provider is not None:
            adapter.config.fallback_provider = fallback_provider
            changes["fallback_provider"] = fallback_provider
        if is_primary is True:
            self._type_primary[adapter.integration_type] = provider_name
            changes["is_primary"] = True

        await integration_audit_service.log_action(
            action="UPDATE_CONFIGURATION",
            actor_id=actor_id,
            actor_role="ADMIN",
            integration_id=f"int_{provider_name.lower()}",
            provider_name=provider_name,
            integration_type=adapter.integration_type,
            status="SUCCESS",
            details=changes,
        )

        return adapter.config

    async def initialize_defaults(self) -> None:
        """Seed and initialize default integration adapters for all supported categories."""
        if self._initialized:
            return

        # Maps Adapters
        dev_maps = DevMapsAdapter()
        osm_maps = OpenStreetMapAdapter()
        google_maps = GoogleMapsAdapter()
        mapbox_maps = MapboxAdapter()
        self.register_adapter(dev_maps, is_primary=True)
        self.register_adapter(osm_maps, is_primary=False)
        self.register_adapter(google_maps, is_primary=False)
        self.register_adapter(mapbox_maps, is_primary=False)

        # Communication Adapters
        sms_adapter = SMSAdapter("DEV_SMS_ADAPTER", is_real_provider=False)
        voice_adapter = VoiceAdapter("DEV_VOICE_ADAPTER", is_real_provider=False)
        email_adapter = EmailAdapter("DEV_EMAIL_ADAPTER", is_real_provider=False)
        push_adapter = PushAdapter("DEV_PUSH_ADAPTER", is_real_provider=False)
        self.register_adapter(sms_adapter, is_primary=True)
        self.register_adapter(voice_adapter, is_primary=True)
        self.register_adapter(email_adapter, is_primary=True)
        self.register_adapter(push_adapter, is_primary=True)

        # Identity / KYC Adapter
        identity_adapter = IdentityProviderAdapter("DEV_IDENTITY_PROVIDER", is_real_provider=False)
        self.register_adapter(identity_adapter, is_primary=True)

        # Weather Adapter
        weather_adapter = DevWeatherAdapter()
        self.register_adapter(weather_adapter, is_primary=True)

        # Translation Adapter
        trans_adapter = TranslationAdapter("DEV_TRANSLATION_ADAPTER", is_real_provider=False)
        self.register_adapter(trans_adapter, is_primary=True)

        # Emergency CAD Adapter
        emergency_adapter = EmergencyServiceAdapter("DEV_EMERGENCY_CAD_ADAPTER", is_real_provider=False)
        self.register_adapter(emergency_adapter, is_primary=True)

        # Government Adapter
        gov_adapter = GovernmentAuthorityAdapter("DEV_GOVERNMENT_ADAPTER", is_real_provider=False)
        self.register_adapter(gov_adapter, is_primary=True)

        # Tourism Adapter
        tourism_adapter = TourismDataAdapter("DEV_TOURISMDATA_ADAPTER", is_real_provider=False)
        self.register_adapter(tourism_adapter, is_primary=True)

        # Document Vault Adapter
        doc_adapter = DocumentAdapter("DEV_DOCUMENT_VAULT", is_real_provider=False)
        self.register_adapter(doc_adapter, is_primary=True)

        self._initialized = True
        logger.info("IntegrationRegistry: Initialized all default adapters.")


# Global Registry Singleton
integration_registry = IntegrationRegistry()
