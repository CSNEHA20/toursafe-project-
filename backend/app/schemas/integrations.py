from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IntegrationType(str, Enum):
    MAPS = "MAPS"
    ROUTING = "ROUTING"
    GEOCODING = "GEOCODING"
    NOTIFICATION = "NOTIFICATION"
    SMS = "SMS"
    VOICE = "VOICE"
    EMAIL = "EMAIL"
    PUSH = "PUSH"
    IDENTITY = "IDENTITY"
    KYC = "KYC"
    WEATHER = "WEATHER"
    TRANSLATION = "TRANSLATION"
    DOCUMENT = "DOCUMENT"
    EMERGENCY_SERVICE = "EMERGENCY_SERVICE"
    GOVERNMENT = "GOVERNMENT"
    TOURISM = "TOURISM"
    ANALYTICS = "ANALYTICS"
    AI = "AI"
    OTHER = "OTHER"


class IntegrationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    DISABLED = "DISABLED"


class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class IntegrationEnvironment(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"


class IntegrationErrorCode(str, Enum):
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"
    INVALID_REQUEST = "INVALID_REQUEST"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    SSRF_BLOCKED = "SSRF_BLOCKED"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    CONFLICT = "CONFLICT"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"


class IntegrationHealthStatus(BaseModel):
    status: IntegrationStatus = IntegrationStatus.ACTIVE
    is_healthy: bool = True
    latency_ms: float = 0.0
    last_successful_request: Optional[str] = None
    last_failure: Optional[str] = None
    consecutive_failures: int = 0
    circuit_state: CircuitBreakerState = CircuitBreakerState.CLOSED
    detail: str = "Provider operational"
    checked_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class IntegrationConfig(BaseModel):
    provider_name: str
    integration_type: IntegrationType
    environment: IntegrationEnvironment = IntegrationEnvironment.DEVELOPMENT
    enabled: bool = True
    is_primary: bool = True
    fallback_provider: Optional[str] = None
    endpoint_url: Optional[str] = None
    timeout_seconds: float = 5.0
    connect_timeout_seconds: float = 2.0
    max_retries: int = 3
    retry_backoff_factor: float = 1.5
    rate_limit_per_minute: int = 120
    circuit_failure_threshold: int = 5
    circuit_recovery_cooldown_seconds: float = 30.0
    allowlist_domains: List[str] = Field(default_factory=lambda: [
        "api.openstreetmap.org",
        "api.weatherapi.com",
        "api.twilio.com",
        "api.sendgrid.com",
        "api.mapbox.com",
        "maps.googleapis.com",
        "cad.emergency.local",
        "gov.tourism.local",
    ])
    custom_settings: Dict[str, Any] = Field(default_factory=dict)
    api_key_configured: bool = False
    client_secret_configured: bool = False
    webhook_secret_configured: bool = False


class IntegrationRegistration(BaseModel):
    integration_id: str
    provider_name: str
    integration_type: IntegrationType
    status: IntegrationStatus = IntegrationStatus.ACTIVE
    environment: IntegrationEnvironment = IntegrationEnvironment.DEVELOPMENT
    is_real_provider: bool = False
    capabilities: List[str] = Field(default_factory=list)
    configuration: IntegrationConfig
    health: IntegrationHealthStatus
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class IntegrationAuditEntry(BaseModel):
    audit_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action: str
    integration_id: Optional[str] = None
    provider_name: Optional[str] = None
    integration_type: Optional[IntegrationType] = None
    actor_id: str
    actor_role: str
    correlation_id: str
    status: str  # SUCCESS, FAILED, BLOCKED
    latency_ms: Optional[float] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class DeadLetterRecord(BaseModel):
    record_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    operation_name: str
    integration_id: str
    provider_name: str
    integration_type: IntegrationType
    idempotency_key: str
    correlation_id: str
    attempt_count: int
    max_attempts: int
    error_code: str
    error_message: str
    payload_summary: Dict[str, Any] = Field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None


class OutboundEventEnvelope(BaseModel):
    event_id: str
    event_type: str
    event_version: str = "1.0.0"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "toursafe.core"
    correlation_id: str
    payload: Dict[str, Any]
    signature: Optional[str] = None


class InboundWebhookResult(BaseModel):
    success: bool
    status: str
    event_type: str
    event_id: Optional[str] = None
    processed: bool = True
    duplicate: bool = False
    message: str
    normalized_event: Optional[Dict[str, Any]] = None


# Normalized Specific Adapter Schemas

class GeocodingResult(BaseModel):
    formatted_address: str
    latitude: float
    longitude: float
    confidence: float
    provider: str
    place_id: Optional[str] = None
    attribution: str


class ReverseGeocodingResult(BaseModel):
    formatted_address: str
    locality: Optional[str] = None
    administrative_area: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    provider: str
    attribution: str


class RouteStep(BaseModel):
    instruction: str
    distance_meters: float
    duration_seconds: float


class RoutingResult(BaseModel):
    origin: List[float]  # [lon, lat]
    destination: List[float]  # [lon, lat]
    distance_meters: float
    duration_seconds: float
    duration_in_traffic_seconds: Optional[float] = None
    eta_timestamp: str
    geometry_geojson: Dict[str, Any]
    steps: List[RouteStep] = Field(default_factory=list)
    provider: str
    is_fallback: bool = False
    attribution: str


class WeatherCondition(BaseModel):
    temperature_celsius: float
    feels_like_celsius: float
    humidity_percent: float
    wind_speed_kmh: float
    wind_direction: str
    precipitation_mm: float
    visibility_km: float
    uv_index: float
    condition_text: str
    condition_code: str
    is_hazardous: bool = False
    safety_bulletin: Optional[str] = None
    observed_at: str
    provider: str
    attribution: str


class SevereWeatherAlert(BaseModel):
    alert_id: str
    severity: str  # MINOR, MODERATE, SEVERE, EXTREME
    headline: str
    description: str
    effective_from: str
    expires_at: str
    affected_area: str
    provider: str


class TranslationResult(BaseModel):
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    provider: str
    confidence: float
    untranslated_tokens: List[str] = Field(default_factory=list)


class ExternalEmergencyRequest(BaseModel):
    external_system: str
    external_incident_id: Optional[str] = None
    toursafe_incident_id: str
    severity: str
    incident_type: str
    fuzzed_latitude: float
    fuzzed_longitude: float
    location_description: str
    description: str
    responder_units_requested: int = 1
    contact_name_masked: str
    status: str  # DISPATCHED, ACKNOWLEDGED, EN_ROUTE, ON_SCENE, RESOLVED, CANCELLED
    synced_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ExternalStateConflict(BaseModel):
    conflict_id: str
    toursafe_incident_id: str
    external_system: str
    external_incident_id: str
    toursafe_status: str
    external_status: str
    detected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved: bool = False
    resolution_policy: Optional[str] = None
    resolved_status: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[str] = None
