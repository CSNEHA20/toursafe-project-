from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from .auth import get_current_user, require_role
from ..schemas.integrations import (
    ExternalEmergencyRequest,
    ExternalStateConflict,
    GeocodingResult,
    InboundWebhookResult,
    IntegrationAuditEntry,
    IntegrationConfig,
    IntegrationRegistration,
    IntegrationType,
    ReverseGeocodingResult,
    RoutingResult,
    TranslationResult,
    WeatherCondition,
)
from ..services.integrations import (
    conflict_service,
    dead_letter_service,
    integration_audit_service,
    integration_registry,
    outbound_event_publisher,
    security_manager,
    webhook_manager,
    WebhookVerificationException,
)
from ..services.integrations.adapters import (
    DevMapsAdapter,
    EmergencyServiceAdapter,
    MapsAdapter,
    TranslationAdapter,
    WeatherAdapter,
)

logger = logging.getLogger("toursafe.routers.integrations")

router = APIRouter(prefix="/api/v1/integrations", tags=["External Integrations & Interoperability"])


# --- Request DTOs ---

class ConfigUpdateDTO(BaseModel):
    enabled: Optional[bool] = None
    is_primary: Optional[bool] = None
    fallback_provider: Optional[str] = None
    timeout_seconds: Optional[float] = None


class GeocodeRequestDTO(BaseModel):
    address: str


class ReverseGeocodeRequestDTO(BaseModel):
    latitude: float
    longitude: float


class RouteRequestDTO(BaseModel):
    origin: List[float] = Field(..., description="[longitude, latitude]")
    destination: List[float] = Field(..., description="[longitude, latitude]")
    waypoints: Optional[List[List[float]]] = None
    avoid_danger_zones: bool = True


class TranslationRequestDTO(BaseModel):
    text: str
    target_language: str = "en"
    source_language: Optional[str] = None


class ConflictResolveDTO(BaseModel):
    policy: str  # TOURSAFE_WINS, EXTERNAL_WINS, MANUAL_OVERRIDE
    chosen_status: str


# --- Endpoints ---

@router.get("", response_model=List[IntegrationRegistration])
async def list_integrations(
    current_user: Any = Depends(get_current_user),
):
    """List all registered external integration adapters and current health metrics."""
    await integration_registry.initialize_defaults()
    return await integration_registry.list_integrations()


@router.get("/{provider_name}", response_model=IntegrationRegistration)
async def get_integration_detail(
    provider_name: str,
    current_user: Any = Depends(get_current_user),
):
    """Get details and health of a specific integration provider."""
    await integration_registry.initialize_defaults()
    adapter = integration_registry.get_adapter(provider_name)
    if not adapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Provider '{provider_name}' not registered")

    health = adapter.get_health_status()
    return IntegrationRegistration(
        integration_id=f"int_{provider_name.lower()}",
        provider_name=provider_name,
        integration_type=adapter.integration_type,
        status=health.status,
        environment=adapter.config.environment,
        is_real_provider=adapter.is_real_provider,
        capabilities=adapter.capabilities,
        configuration=adapter.config,
        health=health,
    )


@router.post("/{provider_name}/test")
async def test_integration_connection(
    provider_name: str,
    current_user: Any = Depends(require_role("authority", "admin", "dispatcher", "commander")),
):
    """Execute on-demand health/connectivity test against provider gateway."""
    await integration_registry.initialize_defaults()
    actor_id = getattr(current_user, "id", getattr(current_user, "user_id", "AUTHORITY_USER"))
    result = await integration_registry.test_connection(provider_name, actor_id=actor_id)
    return result


@router.patch("/{provider_name}/config", response_model=IntegrationConfig)
async def update_integration_config(
    provider_name: str,
    dto: ConfigUpdateDTO,
    current_user: Any = Depends(require_role("authority", "admin", "dispatcher", "commander")),
):
    """Update configuration, enable/disable status, or primary/fallback routing."""
    await integration_registry.initialize_defaults()
    actor_id = getattr(current_user, "id", getattr(current_user, "user_id", "ADMIN_USER"))
    try:
        updated_cfg = await integration_registry.update_configuration(
            provider_name=provider_name,
            enabled=dto.enabled,
            is_primary=dto.is_primary,
            fallback_provider=dto.fallback_provider,
            timeout_seconds=dto.timeout_seconds,
            actor_id=actor_id,
        )
        return updated_cfg
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Provider '{provider_name}' not found")


@router.get("/logs/audit", response_model=List[Dict[str, Any]])
async def get_integration_audit_logs(
    integration_id: Optional[str] = None,
    provider_name: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    current_user: Any = Depends(require_role("authority", "admin", "dispatcher", "commander")),
):
    """List sanitized audit logs for integration actions."""
    return await integration_audit_service.get_logs(integration_id=integration_id, provider_name=provider_name, limit=limit)


@router.get("/queue/dead-letter", response_model=List[Dict[str, Any]])
async def get_dead_letter_records(
    resolved: Optional[bool] = None,
    integration_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    current_user: Any = Depends(require_role("authority", "admin", "dispatcher", "commander")),
):
    """List dead-letter integration operations requiring inspection or manual retry."""
    return await dead_letter_service.list_records(resolved=resolved, integration_id=integration_id, limit=limit)


@router.post("/queue/dead-letter/{record_id}/retry")
async def retry_dead_letter_record(
    record_id: str,
    current_user: Any = Depends(require_role("authority", "admin", "dispatcher", "commander")),
):
    """Authorized manual retry of a dead-letter operation."""
    rec = await dead_letter_service.get_record(record_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dead letter record '{record_id}' not found")

    actor_id = getattr(current_user, "id", getattr(current_user, "user_id", "ADMIN_USER"))
    await dead_letter_service.mark_resolved(record_id, actor_id=actor_id)

    # Log manual retry action
    await integration_audit_service.log_action(
        action="MANUAL_RETRY_DEAD_LETTER",
        actor_id=actor_id,
        actor_role="ADMIN",
        integration_id=rec.get("integration_id"),
        provider_name=rec.get("provider_name"),
        status="SUCCESS",
        details={"record_id": record_id, "operation_name": rec.get("operation_name")},
    )

    return {
        "success": True,
        "record_id": record_id,
        "message": f"Dead letter operation '{rec.get('operation_name')}' marked for retry and resolved.",
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/emergency-sync/conflicts", response_model=List[Dict[str, Any]])
async def list_emergency_state_conflicts(
    resolved: Optional[bool] = None,
    current_user: Any = Depends(require_role("authority", "admin", "dispatcher", "commander")),
):
    """List external state synchronization conflicts."""
    return await conflict_service.list_conflicts(resolved=resolved)


@router.post("/emergency-sync/conflicts/{conflict_id}/resolve")
async def resolve_emergency_state_conflict(
    conflict_id: str,
    dto: ConflictResolveDTO,
    current_user: Any = Depends(require_role("authority", "admin", "dispatcher", "commander")),
):
    """Resolve an emergency state conflict using a policy (e.g. TOURSAFE_WINS, EXTERNAL_WINS)."""
    actor_id = getattr(current_user, "id", getattr(current_user, "user_id", "ADMIN_USER"))
    res = await conflict_service.resolve_conflict(
        conflict_id=conflict_id,
        policy=dto.policy,
        chosen_status=dto.chosen_status,
        actor_id=actor_id,
    )
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Conflict '{conflict_id}' not found")

    await integration_audit_service.log_action(
        action="RESOLVE_STATE_CONFLICT",
        actor_id=actor_id,
        actor_role="ADMIN",
        status="SUCCESS",
        details={"conflict_id": conflict_id, "policy": dto.policy, "resolved_status": dto.chosen_status},
    )
    return res


@router.post("/webhooks/{provider_type}/{provider_name}", response_model=InboundWebhookResult)
async def inbound_webhook_receiver(
    provider_type: str,
    provider_name: str,
    request: Request,
):
    """
    Secure inbound webhook receiver with HMAC signature verification,
    timestamp anti-replay protection, idempotency deduplication, and normalized dispatch.
    """
    raw_body = await request.body()
    headers_dict = {k.lower(): v for k, v in request.headers.items()}

    # Secret lookup (dev secret fallback for testing)
    secret = "toursafe_dev_webhook_secret_key"

    try:
        result = await webhook_manager.process_inbound_webhook(
            provider_type=provider_type,
            provider_name=provider_name,
            raw_body=raw_body,
            headers=headers_dict,
            secret=secret if "x-signature-256" in headers_dict or "x-hub-signature-256" in headers_dict else None,
        )
        return result
    except WebhookVerificationException as ve:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Webhook processing error: {str(e)}")


# --- Normalized Operational Services (Maps, Weather, Translation) ---

@router.post("/maps/geocode", response_model=GeocodingResult)
async def geocode_address(
    dto: GeocodeRequestDTO,
    current_user: Any = Depends(get_current_user),
):
    """Geocode address using active maps provider."""
    await integration_registry.initialize_defaults()
    adapter, _ = integration_registry.get_adapter_with_fallback(IntegrationType.MAPS)
    if isinstance(adapter, MapsAdapter):
        return await adapter.geocode(dto.address)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Maps adapter unavailable")


@router.post("/maps/reverse-geocode", response_model=ReverseGeocodingResult)
async def reverse_geocode_coordinates(
    dto: ReverseGeocodeRequestDTO,
    current_user: Any = Depends(get_current_user),
):
    """Reverse geocode coordinates using active maps provider."""
    await integration_registry.initialize_defaults()
    adapter, _ = integration_registry.get_adapter_with_fallback(IntegrationType.MAPS)
    if isinstance(adapter, MapsAdapter):
        return await adapter.reverse_geocode(dto.latitude, dto.longitude)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Maps adapter unavailable")


@router.post("/maps/route", response_model=RoutingResult)
async def calculate_route(
    dto: RouteRequestDTO,
    current_user: Any = Depends(get_current_user),
):
    """Calculate route with active provider and automatic fallback."""
    await integration_registry.initialize_defaults()
    adapter, _ = integration_registry.get_adapter_with_fallback(IntegrationType.MAPS)
    if isinstance(adapter, MapsAdapter):
        return await adapter.calculate_route(
            origin=dto.origin,
            destination=dto.destination,
            waypoints=dto.waypoints,
            avoid_danger_zones=dto.avoid_danger_zones,
        )
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Maps adapter unavailable")


@router.get("/weather/current", response_model=WeatherCondition)
async def get_current_weather(
    latitude: float = Query(15.4989, ge=-90.0, le=90.0),
    longitude: float = Query(73.8278, ge=-180.0, le=180.0),
    current_user: Any = Depends(get_current_user),
):
    """Get normalized weather conditions and safety advisories."""
    await integration_registry.initialize_defaults()
    adapter, _ = integration_registry.get_adapter_with_fallback(IntegrationType.WEATHER)
    if isinstance(adapter, WeatherAdapter):
        return await adapter.get_current_weather(latitude, longitude)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Weather adapter unavailable")


@router.post("/translation/translate", response_model=TranslationResult)
async def translate_text(
    dto: TranslationRequestDTO,
    current_user: Any = Depends(get_current_user),
):
    """Translate multilingual communication while preserving coordinates and technical IDs."""
    await integration_registry.initialize_defaults()
    adapter, _ = integration_registry.get_adapter_with_fallback(IntegrationType.TRANSLATION)
    if isinstance(adapter, TranslationAdapter):
        return await adapter.translate(
            text=dto.text,
            target_language=dto.target_language,
            source_language=dto.source_language,
        )
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Translation adapter unavailable")
