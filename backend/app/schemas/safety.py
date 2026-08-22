import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class SignalType(str, Enum):
    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    ANOMALY_CLEARED = "ANOMALY_CLEARED"
    ZONE_ENTERED = "ZONE_ENTERED"
    ZONE_EXITED = "ZONE_EXITED"
    ZONE_DWELL = "ZONE_DWELL"
    GPS_LOCATION_UPDATE = "GPS_LOCATION_UPDATE"
    GPS_STALE = "GPS_STALE"
    GPS_UNCERTAIN = "GPS_UNCERTAIN"
    TELEMETRY_GOOD = "TELEMETRY_GOOD"
    TELEMETRY_DEGRADED = "TELEMETRY_DEGRADED"
    TELEMETRY_OFFLINE = "TELEMETRY_OFFLINE"
    TRACKING_ACTIVE = "TRACKING_ACTIVE"
    TRACKING_STOPPED = "TRACKING_STOPPED"
    ITINERARY_DEVIATION = "ITINERARY_DEVIATION"
    TEMPORAL_CONTEXT = "TEMPORAL_CONTEXT"
    TRIP_CONTEXT = "TRIP_CONTEXT"
    HISTORICAL_CONTEXT = "HISTORICAL_CONTEXT"


class SignalQuality(str, Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    POOR = "POOR"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class SafetyState(str, Enum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    ELEVATED = "ELEVATED"
    INCIDENT_CANDIDATE = "INCIDENT_CANDIDATE"
    INCIDENT = "INCIDENT"
    RECOVERING = "RECOVERING"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


class ConfidenceClass(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ASSESSING = "ASSESSING"
    ASSIGNED = "ASSIGNED"
    RESPONDING = "RESPONDING"
    MONITORING = "MONITORING"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"


class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentSource(str, Enum):
    MANUAL_SOS = "MANUAL_SOS"
    SAFETY_ENGINE = "SAFETY_ENGINE"
    AUTHORITY_CREATED = "AUTHORITY_CREATED"


class SafetySignal(BaseModel):
    """
    Canonical internal safety signal representation across all TourSafe subsystems.
    """
    signal_id: str = Field(default_factory=lambda: f"sig_{uuid.uuid4().hex[:12]}")
    signal_type: SignalType
    tourist_id: str
    session_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str
    value: Any
    quality: SignalQuality = SignalQuality.GOOD
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TriggeredRule(BaseModel):
    """
    Detailed audit explanation of a single triggered safety rule.
    """
    rule_id: str
    rule_name: str
    category: str
    contributed_state: SafetyState
    reason: str
    confidence_weight: float = 1.0
    matched_signals: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Multi-Signal Risk Fusion & Intelligence Schemas (Prompt 23)
# ---------------------------------------------------------------------------

class NormalizedSafetyFeatures(BaseModel):
    """
    Standardized scalar feature representation across all 8 input domains [0.0 - 1.0].
    """
    motion_anomaly_norm: float = Field(default=0.0, ge=0.0, le=1.0)
    geospatial_hazard_norm: float = Field(default=0.0, ge=0.0, le=1.0)
    itinerary_deviation_norm: float = Field(default=0.0, ge=0.0, le=1.0)
    telemetry_degradation_norm: float = Field(default=0.0, ge=0.0, le=1.0)
    temporal_risk_norm: float = Field(default=0.0, ge=0.0, le=1.0)
    trip_vulnerability_norm: float = Field(default=0.0, ge=0.0, le=1.0)
    historical_risk_norm: float = Field(default=0.0, ge=0.0, le=1.0)
    kinematic_shock_norm: float = Field(default=0.0, ge=0.0, le=1.0)


class RiskScoreBreakdown(BaseModel):
    """
    Multi-layer risk score decomposition (0 - 100 scale).
    """
    composite_risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    motion_risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    spatial_risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    itinerary_risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    environmental_risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    vulnerability_risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    risk_level_label: str = "SAFE"  # "SAFE", "WATCH", "ELEVATED", "CRITICAL"
    risk_trend: str = "STABLE"  # "INCREASING", "STABLE", "DECREASING"


class SignalCorrelationResult(BaseModel):
    """
    Cross-signal correlation patterns and false-positive reduction evaluation.
    """
    correlated_pattern: str = "NONE"
    dampening_factor: float = Field(default=1.0, ge=0.0, le=1.0)
    false_positive_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    is_false_alarm_suppressed: bool = False
    matched_signatures: List[str] = Field(default_factory=list)
    correlation_notes: List[str] = Field(default_factory=list)


class ConfidenceAssessment(BaseModel):
    """
    Uncertainty quantification and confidence scoring.
    """
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence_class: ConfidenceClass = ConfidenceClass.HIGH
    sensor_uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    sparsity_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    cross_signal_conflict: float = Field(default=0.0, ge=0.0, le=1.0)
    freshness_penalty: float = Field(default=0.0, ge=0.0, le=1.0)


class FeatureAttribution(BaseModel):
    """
    SHAP-style or linear weight contribution for individual risk factors.
    """
    feature_name: str
    contribution_score: float
    percentage: float
    direction: str  # "INCREASES_RISK", "MITIGATES_RISK", "NEUTRAL"
    description: str


class ExplainabilityReport(BaseModel):
    """
    Comprehensive explainability breakdown for operators and tourists.
    """
    primary_risk_drivers: List[str] = Field(default_factory=list)
    mitigating_factors: List[str] = Field(default_factory=list)
    feature_attributions: List[FeatureAttribution] = Field(default_factory=list)
    natural_language_summary: str = ""
    tourist_guidance: str = ""


class DecisionSupportRecommendation(BaseModel):
    """
    Prescriptive decision support and actionable recommendations for authorities/dispatchers.
    """
    recommended_action: str = "MONITOR_STANDARD"
    action_priority: str = "LOW"  # "LOW", "MEDIUM", "HIGH", "URGENT"
    verification_checklist: List[str] = Field(default_factory=list)
    sensor_health_advisory: Optional[str] = None
    suggested_responder_type: Optional[str] = None


class MultiSignalRiskAssessment(BaseModel):
    """
    Complete, unified risk fusion intelligence envelope.
    """
    assessment_id: str = Field(default_factory=lambda: f"ass_{uuid.uuid4().hex[:12]}")
    tourist_id: str
    session_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    normalized_features: NormalizedSafetyFeatures = Field(default_factory=NormalizedSafetyFeatures)
    risk_breakdown: RiskScoreBreakdown = Field(default_factory=RiskScoreBreakdown)
    correlation: SignalCorrelationResult = Field(default_factory=SignalCorrelationResult)
    confidence: ConfidenceAssessment = Field(default_factory=ConfidenceAssessment)
    explainability: ExplainabilityReport = Field(default_factory=ExplainabilityReport)
    decision_support: DecisionSupportRecommendation = Field(default_factory=DecisionSupportRecommendation)
    raw_signals_count: int = 0


# ---------------------------------------------------------------------------
# Decision & Active State Models
# ---------------------------------------------------------------------------

class SafetyDecision(BaseModel):
    """
    Immutable explainable safety decision generated by the rule and risk fusion engine.
    """
    decision_id: str = Field(default_factory=lambda: f"dec_{uuid.uuid4().hex[:12]}")
    tourist_id: str
    session_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    state: SafetyState
    previous_state: SafetyState
    rule_version: str = "safety-rules-v1"
    triggered_rules: List[TriggeredRule] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    signals: Dict[str, Any] = Field(default_factory=dict)
    quality: SignalQuality = SignalQuality.GOOD
    confidence_class: ConfidenceClass = ConfidenceClass.HIGH
    model_versions: Dict[str, str] = Field(default_factory=dict)
    zone_versions: Dict[str, str] = Field(default_factory=dict)
    risk_score: Optional[float] = None
    risk_assessment: Optional[MultiSignalRiskAssessment] = None
    expires_at: Optional[str] = None


class ActiveSafetyState(BaseModel):
    """
    Cached active safety state in Redis for fast inspection.
    """
    tourist_id: str
    current_state: SafetyState
    previous_state: SafetyState
    decision_id: str
    started_at: str
    last_update: str
    rule_version: str
    confidence_class: ConfidenceClass
    active_reasons: List[str] = Field(default_factory=list)
    active_signals_summary: Dict[str, Any] = Field(default_factory=dict)
    active_incident_id: Optional[str] = None
    recovery_started_at: Optional[str] = None
    risk_score: Optional[float] = None
    risk_assessment: Optional[MultiSignalRiskAssessment] = None


class IncidentRecord(BaseModel):
    """
    Persistent safety incident record with full lifecycle tracking.
    """
    incident_id: str = Field(default_factory=lambda: f"inc_{uuid.uuid4().hex[:12]}")
    tourist_id: str
    session_id: Optional[str] = None
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    status: IncidentStatus = IncidentStatus.OPEN
    severity: IncidentSeverity = IncidentSeverity.HIGH
    source: IncidentSource = IncidentSource.SAFETY_ENGINE
    decision_id: str = "none"
    rule_version: str = "safety-rules-v1"
    reasons: List[str] = Field(default_factory=list)
    signal_summary: Dict[str, Any] = Field(default_factory=dict)
    risk_score: Optional[float] = None
    risk_assessment: Optional[MultiSignalRiskAssessment] = None
    notes: Optional[str] = None
    notes_list: List[Dict[str, Any]] = Field(default_factory=list)
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    location_data: Optional[Dict[str, Any]] = None
    assigned_to: Optional[str] = None  # responder_id or authority operator
    assigned_unit: Optional[str] = None
    responder_type: Optional[str] = None
    escalation_stage: int = 0
    escalation_history: List[Dict[str, Any]] = Field(default_factory=list)
    notifications_sent: List[Dict[str, Any]] = Field(default_factory=list)
    resolution_category: Optional[str] = None
    resolution_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    closed_at: Optional[str] = None
    closed_by: Optional[str] = None
    version: int = 1  # Optimistic concurrency locking
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------

class TouristSafetyStatusResponse(BaseModel):
    """
    Sanitized tourist-facing safety status. Excludes internal model weights and rule IDs,
    provides friendly score rating and guidance.
    """
    safety_status: str  # "Normal", "Monitoring", "Attention Required", "Connection Degraded", "Unknown"
    monitoring_active: bool
    gps_connected: bool
    last_checked_at: str
    zone_name: Optional[str] = None
    zone_risk: Optional[str] = None
    guidance_message: str
    safety_index: Optional[float] = None  # 0-100 score where 100 is completely safe
    risk_level: Optional[str] = None
    proactive_check_required: bool = False
    proactive_check_message: Optional[str] = None


class AuthoritySafetyStatusResponse(BaseModel):
    """
    Full operational safety snapshot for Authority Operations with deep risk fusion metrics.
    """
    tourist_id: str
    current_state: SafetyState
    previous_state: SafetyState
    decision_id: str
    started_at: str
    last_update: str
    rule_version: str
    confidence_class: ConfidenceClass
    active_reasons: List[str]
    active_signals: Dict[str, Any]
    active_incident: Optional[IncidentRecord] = None
    model_version: Optional[str] = None
    recovery_started_at: Optional[str] = None
    risk_score: Optional[float] = None
    risk_assessment: Optional[MultiSignalRiskAssessment] = None


class IncidentAcknowledgeRequest(BaseModel):
    notes: Optional[str] = None


class IncidentResolveRequest(BaseModel):
    resolution_reason: str = Field(..., min_length=3, description="Mandatory reason for closing the safety incident")
    notes: Optional[str] = None


class IncidentListResponse(BaseModel):
    incidents: List[IncidentRecord]
    total: int
    page: int
    limit: int


class SafetyHistoryResponse(BaseModel):
    tourist_id: str
    decisions: List[SafetyDecision]
    total: int


class SafetyCheckResponseRequest(BaseModel):
    """
    Tourist response to an active safety check prompt.
    """
    response_type: str = Field(..., description="'SAFE_CONFIRMED', 'ASSISTANCE_REQUESTED', 'FALSE_ALARM', 'CUSTOM_MESSAGE'")
    user_note: Optional[str] = None
    battery_level: Optional[float] = None
    timestamp: Optional[str] = None


class SafetyCheckResponseResult(BaseModel):
    success: bool
    message: str
    updated_state: SafetyState
    risk_score: float
    guidance: str


class RiskMatrixConfigResponse(BaseModel):
    """
    Authority inspection schema for risk weights, thresholds, and correlation patterns.
    """
    rule_version: str
    weights: Dict[str, float]
    thresholds: Dict[str, float]
    correlation_signatures: List[Dict[str, Any]]
    dampening_factors: Dict[str, float]
    zone_risk_levels: Dict[str, int]
