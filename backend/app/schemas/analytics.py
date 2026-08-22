"""
TourSafe Analytics Domain Schemas and Models (Prompt 26)

Pydantic v2 schemas defining analytical requests, filters, time-bucketing,
operational KPIs, zone intelligence, incident metrics, safety state analysis,
anomaly conversion, responder operational statistics, notification health,
data quality scoring, heatmaps, geospatial intelligence, demand forecasting,
operational recommendations, analytics alerts, and export job models.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class TimeGranularity(str, Enum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class TimeWindowType(str, Enum):
    LIVE = "LIVE"
    TODAY = "TODAY"
    LAST_24_HOURS = "LAST_24_HOURS"
    LAST_7_DAYS = "LAST_7_DAYS"
    LAST_30_DAYS = "LAST_30_DAYS"
    CUSTOM = "CUSTOM"


class HeatmapMetricType(str, Enum):
    TOURIST_DENSITY = "tourist_density"
    ZONE_VISITS = "zone_visits"
    INCIDENTS = "incidents"
    SOS_EVENTS = "sos_events"
    ANOMALIES = "anomalies"
    RESPONSE_ACTIVITY = "response_activity"
    RISK_EPISODES = "risk_episodes"


class QualityStatus(str, Enum):
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    POOR = "POOR"
    UNKNOWN = "UNKNOWN"


class ForecastHorizon(str, Enum):
    NEXT_HOUR = "next_hour"
    NEXT_DAY = "next_day"
    NEXT_WEEK = "next_week"


class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"


class ExportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Filter and Query Request Models
# ---------------------------------------------------------------------------

class AnalyticsFilterParams(BaseModel):
    start_time: Optional[str] = Field(
        default=None,
        description="ISO8601 UTC start datetime filter"
    )
    end_time: Optional[str] = Field(
        default=None,
        description="ISO8601 UTC end datetime filter"
    )
    time_window: Optional[TimeWindowType] = Field(
        default=None,
        description="Named time window (LIVE, TODAY, LAST_24_HOURS, LAST_7_DAYS, LAST_30_DAYS, CUSTOM)"
    )
    timezone: Optional[str] = Field(
        default="UTC",
        description="Client / Authority timezone for presentation (e.g. UTC, Asia/Kolkata, America/New_York)"
    )
    granularity: TimeGranularity = Field(
        default=TimeGranularity.DAY,
        description="Time aggregation granularity"
    )
    jurisdiction_id: Optional[str] = None
    zone_id: Optional[str] = None
    risk_level: Optional[str] = None
    incident_source: Optional[str] = None
    incident_type: Optional[str] = None
    severity: Optional[str] = None
    model_version: Optional[str] = None
    responder_id: Optional[str] = None
    unit_id: Optional[str] = None
    responder_type: Optional[str] = None
    bypass_cache: bool = Field(default=False, description="Force fresh aggregation bypass")


# ---------------------------------------------------------------------------
# Freshness & Metadata Models
# ---------------------------------------------------------------------------

class DataFreshnessMeta(BaseModel):
    data_updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data_range_start: Optional[str] = None
    data_range_end: Optional[str] = None
    freshness_seconds: float = 0.0
    freshness_status: str = "LIVE"  # LIVE, UPDATED_RECENTLY, STALE, CONNECTION_LOST
    aggregation_level: str = "canonical_db"
    is_cached: bool = False
    sample_size: int = 0
    data_status: str = "REAL_DATA"  # REAL_DATA, PARTIAL_DATA, INSUFFICIENT_DATA, UNKNOWN
    timezone: str = "UTC"


# ---------------------------------------------------------------------------
# Time-series Point Models
# ---------------------------------------------------------------------------

class TimeSeriesPoint(BaseModel):
    timestamp: str  # Bucket start ISO timestamp
    count: int = 0
    value: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MetricComparison(BaseModel):
    current_value: float
    previous_value: Optional[float] = None
    absolute_change: Optional[float] = None
    percentage_change: Optional[float] = None
    status: str = "AVAILABLE"  # AVAILABLE, NO_COMPARISON_DATA, INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# Duration Percentiles Model
# ---------------------------------------------------------------------------

class IncidentDurationMetrics(BaseModel):
    count: int = 0
    p50_seconds: Optional[float] = None
    median_seconds: Optional[float] = None
    p75_seconds: Optional[float] = None
    p90_seconds: Optional[float] = None
    p95_seconds: Optional[float] = None
    p99_seconds: Optional[float] = None
    mean_seconds: Optional[float] = None
    min_seconds: Optional[float] = None
    max_seconds: Optional[float] = None


# ---------------------------------------------------------------------------
# Operational & Executive Overview KPIs (Prompt 26)
# ---------------------------------------------------------------------------

class ResponderOperationalBreakdown(BaseModel):
    total_registered: int = 0
    active_on_shift: int = 0
    available_for_dispatch: int = 0
    assigned_or_responding: int = 0
    offline_or_break: int = 0


class AgingBucket(BaseModel):
    bucket_label: str  # "<5m", "5-15m", "15-30m", "30+m"
    min_minutes: float
    max_minutes: Optional[float] = None
    incident_count: int = 0
    incident_ids: List[str] = Field(default_factory=list)


class SystemHealthSummary(BaseModel):
    status: QualityStatus = QualityStatus.GOOD
    api_latency_p95_ms: float = 0.0
    database_status: str = "HEALTHY"
    redis_status: str = "HEALTHY"
    ml_inference_status: str = "HEALTHY"
    realtime_connection_status: str = "CONNECTED"


class ExecutiveDashboardResponse(BaseModel):
    active_tourists: int = 0
    active_trips: int = 0
    active_tracking_sessions: int = 0
    active_incidents: int = 0
    open_sos_count: int = 0
    responders: ResponderOperationalBreakdown = Field(default_factory=ResponderOperationalBreakdown)
    tourists_in_elevated_safety: int = 0
    active_risk_episodes: int = 0
    incidents_today: int = 0
    response_times: IncidentDurationMetrics = Field(default_factory=IncidentDurationMetrics)
    escalation_rate: float = 0.0
    system_health: SystemHealthSummary = Field(default_factory=SystemHealthSummary)
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)
    incident_trend_today: List[TimeSeriesPoint] = Field(default_factory=list)
    safety_state_distribution: Dict[str, int] = Field(default_factory=dict)
    key_operational_alerts: List[Dict[str, Any]] = Field(default_factory=list)


# Backward compatibility alias
class OperationsOverviewMetrics(BaseModel):
    active_tourists: int = 0
    active_tracking_sessions: int = 0
    tourists_in_elevated_safety: int = 0
    tourists_in_zones: int = 0
    open_incidents: int = 0
    responding_incidents: int = 0
    sos_events_today: int = 0
    total_incidents_in_period: int = 0
    total_anomalies_in_period: int = 0
    median_response_time_seconds: Optional[float] = None
    p90_response_time_seconds: Optional[float] = None
    tracking_coverage_percentage: Optional[float] = None
    gps_availability_percentage: float = 0.0
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)
    incident_trend: List[TimeSeriesPoint] = Field(default_factory=list)
    safety_state_distribution: Dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Incident Analytics (Prompt 26 Enhanced)
# ---------------------------------------------------------------------------

class IncidentAgingAnalysis(BaseModel):
    aging_buckets: List[AgingBucket] = Field(default_factory=list)
    oldest_open_incident_id: Optional[str] = None
    oldest_open_duration_minutes: Optional[float] = None


class IncidentAnalyticsResponse(BaseModel):
    total_incidents: int = 0
    open_incidents: int = 0
    resolved_incidents: int = 0
    closed_incidents: int = 0
    cancelled_incidents: int = 0
    escalated_incidents: int = 0
    false_alarms: int = 0
    false_alarm_rate: float = 0.0
    incident_rate_per_1k_tourists: Optional[float] = None
    by_source: Dict[str, int] = Field(default_factory=dict)  # MANUAL_SOS, SAFETY_ENGINE, AUTHORITY_CREATED
    by_severity: Dict[str, int] = Field(default_factory=dict)  # LOW, MEDIUM, HIGH, CRITICAL
    by_category: Dict[str, int] = Field(default_factory=dict)  # MEDICAL, SECURITY, GEOFENCE, ANOMALY, GENERAL
    by_status: Dict[str, int] = Field(default_factory=dict)
    by_zone: Dict[str, int] = Field(default_factory=dict)
    time_to_acknowledge: IncidentDurationMetrics = Field(default_factory=IncidentDurationMetrics)
    time_to_dispatch: IncidentDurationMetrics = Field(default_factory=IncidentDurationMetrics)
    time_to_assign: IncidentDurationMetrics = Field(default_factory=IncidentDurationMetrics)
    time_to_response: IncidentDurationMetrics = Field(default_factory=IncidentDurationMetrics)
    time_to_arrival: IncidentDurationMetrics = Field(default_factory=IncidentDurationMetrics)
    time_to_resolution: IncidentDurationMetrics = Field(default_factory=IncidentDurationMetrics)
    time_to_close: IncidentDurationMetrics = Field(default_factory=IncidentDurationMetrics)
    aging_analysis: IncidentAgingAnalysis = Field(default_factory=IncidentAgingAnalysis)
    sla_threshold_seconds: Optional[float] = 900.0  # 15 minutes default target
    within_sla_count: int = 0
    outside_sla_count: int = 0
    sla_compliance_rate: Optional[float] = None
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


# ---------------------------------------------------------------------------
# Escalation Analytics
# ---------------------------------------------------------------------------

class EscalationLevelCount(BaseModel):
    level: int  # 0, 1, 2, 3
    level_name: str
    count: int = 0
    avg_time_to_reach_seconds: Optional[float] = None


class EscalationReasonBreakdown(BaseModel):
    reason: str  # NO_ACK, NO_RESPONDER_AVAILABLE, SLA_BREACH, SEVERITY_UPGRADE, MANUAL_OVERRIDE
    count: int = 0
    percentage: float = 0.0


class EscalationAnalyticsResponse(BaseModel):
    total_eligible_incidents: int = 0
    total_escalated_incidents: int = 0
    escalation_rate: float = 0.0
    levels: List[EscalationLevelCount] = Field(default_factory=list)
    reasons: List[EscalationReasonBreakdown] = Field(default_factory=list)
    time_to_escalation: IncidentDurationMetrics = Field(default_factory=IncidentDurationMetrics)
    resolution_post_escalation_rate: float = 0.0
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


# ---------------------------------------------------------------------------
# Geospatial Intelligence & Hotspots
# ---------------------------------------------------------------------------

class HotspotCluster(BaseModel):
    cluster_id: str
    latitude: float
    longitude: float
    radius_meters: float
    intensity_score: float  # 0.0 - 100.0
    incident_count: int = 0
    risk_episode_count: int = 0
    zone_name: Optional[str] = None
    primary_incident_type: Optional[str] = None


class GeospatialHotspotResponse(BaseModel):
    hotspots: List[HotspotCluster] = Field(default_factory=list)
    total_hotspots: int = 0
    hotspot_density_score: float = 0.0
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


class ZoneSummaryMetric(BaseModel):
    zone_id: str
    name: str
    risk_level: str
    zone_type: str
    unique_tourists: int = 0
    total_entries: int = 0
    total_exits: int = 0
    total_dwell_events: int = 0
    avg_dwell_seconds: Optional[float] = None
    max_dwell_seconds: Optional[float] = None
    incident_count: int = 0
    anomaly_count: int = 0
    sos_count: int = 0
    risk_episode_count: int = 0
    active_tourists_now: int = 0
    risk_ranking_score: float = 0.0


class ZoneDetailAnalyticsResponse(BaseModel):
    zone_id: str
    name: str
    risk_level: str
    zone_type: str
    geometry: Optional[Dict[str, Any]] = None
    center: Optional[Dict[str, Any]] = None
    unique_tourists: int = 0
    entries_count: int = 0
    exits_count: int = 0
    dwell_count: int = 0
    average_dwell_seconds: Optional[float] = None
    maximum_dwell_seconds: Optional[float] = None
    incidents_count: int = 0
    sos_count: int = 0
    anomalies_count: int = 0
    risk_episodes_count: int = 0
    hourly_entry_distribution: Dict[str, int] = Field(default_factory=dict)
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


class ZoneListAnalyticsResponse(BaseModel):
    zones: List[ZoneSummaryMetric] = Field(default_factory=list)
    total_zones: int = 0
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


class HeatmapCell(BaseModel):
    geohash: str
    latitude: float
    longitude: float
    weight: float
    sample_count: int
    is_suppressed: bool = False  # Privacy suppression if sample_count < k-threshold


class HeatmapResponse(BaseModel):
    layer_type: HeatmapMetricType
    cells: List[HeatmapCell] = Field(default_factory=list)
    total_cells: int = 0
    suppressed_cells_count: int = 0
    privacy_threshold_k: int = 3
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


class TouristFlowEdge(BaseModel):
    from_zone_id: str
    from_zone_name: str
    to_zone_id: str
    to_zone_name: str
    transition_count: int = 0
    avg_travel_time_seconds: Optional[float] = None


class TouristFlowResponse(BaseModel):
    edges: List[TouristFlowEdge] = Field(default_factory=list)
    total_transitions: int = 0
    peak_corridors: List[str] = Field(default_factory=list)
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


class RouteAnalyticsResponse(BaseModel):
    total_itineraries_analyzed: int = 0
    completed_legs: int = 0
    missed_legs: int = 0
    delayed_legs: int = 0
    deviated_legs: int = 0
    leg_completion_rate: float = 0.0
    deviation_frequency: float = 0.0
    average_dwell_minutes: float = 0.0
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


class DensityAlert(BaseModel):
    alert_id: str
    zone_id: str
    zone_name: str
    current_density_per_sqkm: float
    historical_baseline_density: float
    surge_ratio: float
    severity: str = "INFO"  # INFO, WARNING, ELEVATED
    detected_at: str


class DensityAlertResponse(BaseModel):
    alerts: List[DensityAlert] = Field(default_factory=list)
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


# ---------------------------------------------------------------------------
# Safety & Risk Intelligence
# ---------------------------------------------------------------------------

class RiskEpisodeAnalytics(BaseModel):
    total_episodes: int = 0
    active_episodes: int = 0
    peak_risk_avg: float = 0.0
    peak_confidence_avg: float = 0.0
    avg_duration_seconds: float = 0.0
    recovery_rate: float = 0.0
    incident_conversion_count: int = 0
    operational_conversion_rate: float = 0.0


class SafetyStateAnalyticsResponse(BaseModel):
    total_decisions: int = 0
    state_durations_seconds: Dict[str, float] = Field(default_factory=dict)
    state_counts: Dict[str, int] = Field(default_factory=dict)
    transition_frequencies: Dict[str, int] = Field(default_factory=dict)
    unknown_state_frequency: int = 0
    unknown_state_duration_seconds: float = 0.0
    unknown_state_rate: float = 0.0
    unknown_state_causes: Dict[str, int] = Field(default_factory=dict)
    risk_episodes: RiskEpisodeAnalytics = Field(default_factory=RiskEpisodeAnalytics)
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


# ---------------------------------------------------------------------------
# Anomaly Intelligence & ML Model Performance
# ---------------------------------------------------------------------------

class AnomalyAnalyticsResponse(BaseModel):
    total_anomalies: int = 0
    active_anomalies: int = 0
    cleared_anomalies: int = 0
    persistence_breakdown: Dict[str, int] = Field(
        default_factory=lambda: {"single": 0, "repeated": 0, "persistent": 0}
    )
    by_model_version: Dict[str, int] = Field(default_factory=dict)
    by_zone: Dict[str, int] = Field(default_factory=dict)
    score_distribution: Dict[str, int] = Field(
        default_factory=lambda: {
            "0.0-0.5": 0,
            "0.5-0.7": 0,
            "0.7-0.9": 0,
            "0.9-1.0": 0,
            ">1.0": 0,
        }
    )
    mean_duration_seconds: Optional[float] = None
    median_duration_seconds: Optional[float] = None
    incident_conversion_count: int = 0
    cleared_without_incident_count: int = 0
    operational_conversion_rate: float = 0.0
    frequency_per_active_tourist: float = 0.0
    inference_latency_avg_ms: Optional[float] = None
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


class MLModelPerformanceMetric(BaseModel):
    model_version: str
    status: str
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    roc_auc: Optional[float] = None
    pr_auc: Optional[float] = None
    calibration_error: Optional[float] = None
    drift_detected: bool = False
    drift_affected_features: List[str] = Field(default_factory=list)
    inference_latency_p50_ms: Optional[float] = None
    inference_latency_p95_ms: Optional[float] = None
    inference_latency_p99_ms: Optional[float] = None
    inference_success_rate: float = 100.0


class ModelPerformanceReportResponse(BaseModel):
    active_production_models: List[MLModelPerformanceMetric] = Field(default_factory=list)
    available_versions: List[str] = Field(default_factory=list)
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


# ---------------------------------------------------------------------------
# Responder & SLA Performance
# ---------------------------------------------------------------------------

class ResponderAnalyticsResponse(BaseModel):
    total_responders: int = 0
    active_responders: int = 0
    available_responders: int = 0
    assigned_responders: int = 0
    offline_responders: int = 0
    total_assignments: int = 0
    accepted_assignments: int = 0
    completed_assignments: int = 0
    rejected_assignments: int = 0
    timeout_assignments: int = 0
    rejection_rate: float = 0.0
    acceptance_rate: float = 0.0
    utilization_rate: float = 0.0
    p50_response_time_seconds: Optional[float] = None
    median_response_time_seconds: Optional[float] = None
    p75_response_time_seconds: Optional[float] = None
    p90_response_time_seconds: Optional[float] = None
    p95_response_time_seconds: Optional[float] = None
    p50_arrival_time_seconds: Optional[float] = None
    p90_arrival_time_seconds: Optional[float] = None
    p50_resolution_time_seconds: Optional[float] = None
    p90_resolution_time_seconds: Optional[float] = None
    assignments_by_responder_type: Dict[str, int] = Field(default_factory=dict)
    capability_demand: Dict[str, int] = Field(default_factory=dict)  # MEDICAL, SECURITY, SEARCH_RESCUE, SPECIALIST
    unit_performance: List[Dict[str, Any]] = Field(default_factory=list)
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


# ---------------------------------------------------------------------------
# Notification Analytics
# ---------------------------------------------------------------------------

class NotificationAnalyticsResponse(BaseModel):
    total_created: int = 0
    total_sent: int = 0
    total_delivered: int = 0
    total_failed: int = 0
    delivery_success_rate: float = 0.0
    channel_distribution: Dict[str, int] = Field(default_factory=dict)
    category_distribution: Dict[str, int] = Field(default_factory=dict)
    provider_health: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    dead_letter_count: int = 0
    mean_delivery_latency_ms: Optional[float] = None
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


# ---------------------------------------------------------------------------
# Telemetry Quality & System Health
# ---------------------------------------------------------------------------

class QualityDomainMetric(BaseModel):
    domain: str
    status: QualityStatus
    score: float  # 0.0 to 100.0
    details: Dict[str, Any] = Field(default_factory=dict)
    evaluated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DataQualityDashboardResponse(BaseModel):
    overall_health: QualityStatus
    composite_quality_score: float = 100.0
    gps_quality: QualityDomainMetric
    telemetry_quality: QualityDomainMetric
    imu_quality: QualityDomainMetric
    device_health: QualityDomainMetric
    ml_inference_quality: QualityDomainMetric
    zone_geometry_validity: QualityDomainMetric
    incident_completeness: QualityDomainMetric
    notification_delivery_health: QualityDomainMetric
    data_gaps_identified: List[Dict[str, Any]] = Field(default_factory=list)
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


class SystemPerformanceResponse(BaseModel):
    api_p50_ms: float = 0.0
    api_p95_ms: float = 0.0
    api_p99_ms: float = 0.0
    api_error_rate_4xx: float = 0.0
    api_error_rate_5xx: float = 0.0
    db_query_p95_ms: float = 0.0
    redis_latency_ms: float = 0.0
    ml_inference_p95_ms: float = 0.0
    orchestrator_latency_ms: float = 0.0
    background_jobs_succeeded: int = 0
    background_jobs_failed: int = 0
    background_jobs_retried: int = 0
    services_status: Dict[str, str] = Field(default_factory=dict)
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


# ---------------------------------------------------------------------------
# Baseline Demand Forecasting & Uncertainty Intervals (Prompt 26)
# ---------------------------------------------------------------------------

class ForecastDataPoint(BaseModel):
    timestamp: str
    predicted_value: float
    lower_bound_p10: float
    upper_bound_p90: float
    confidence_level: float = 0.80  # 80% prediction interval


class ForecastDemandResponse(BaseModel):
    metric_name: str  # "incident_volume", "responder_demand", "tourist_density", "notification_load"
    horizon: ForecastHorizon
    status: str = "AVAILABLE"  # AVAILABLE, INSUFFICIENT_DATA
    methodology: str = "baseline_exponential_smoothing_with_seasonal_trend"
    historical_points_used: int = 0
    forecast_points: List[ForecastDataPoint] = Field(default_factory=list)
    resource_gap_detected: bool = False
    resource_pressure_level: str = "NORMAL"  # NORMAL, MODERATE, CRITICAL
    expected_peak_demand: Optional[float] = None
    available_responder_capacity: Optional[int] = None
    message: Optional[str] = None
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


# ---------------------------------------------------------------------------
# Operational Recommendations
# ---------------------------------------------------------------------------

class OperationalRecommendation(BaseModel):
    recommendation_id: str
    category: str  # "RESPONDER_CAPACITY", "ZONE_HOTSPOT", "SURGE_MONITORING", "DATA_QUALITY"
    title: str
    observation: str
    evidence: str
    possible_action: str
    urgency: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OperationalRecommendationsResponse(BaseModel):
    recommendations: List[OperationalRecommendation] = Field(default_factory=list)
    total_recommendations: int = 0
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


# ---------------------------------------------------------------------------
# Analytics Alert Policies & Incidents Surge
# ---------------------------------------------------------------------------

class AnalyticsAlertRecord(BaseModel):
    alert_id: str
    alert_type: str  # "INCIDENT_SURGE", "RESPONDER_CAPACITY_PRESSURE", "SYSTEM_DEGRADATION", "MODEL_DRIFT"
    jurisdiction_id: Optional[str] = None
    severity: str = "WARNING"  # INFO, WARNING, CRITICAL
    title: str
    details: Dict[str, Any] = Field(default_factory=dict)
    threshold_configured: float
    actual_value: float
    triggered_at: str
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
    is_active: bool = True


class AnalyticsAlertListResponse(BaseModel):
    alerts: List[AnalyticsAlertRecord] = Field(default_factory=list)
    active_count: int = 0
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


# ---------------------------------------------------------------------------
# Metric Catalog Models
# ---------------------------------------------------------------------------

class MetricDefinitionItem(BaseModel):
    metric_key: str
    name: str
    domain: str
    definition: str
    source_collection: str
    formula: str
    supported_filters: List[str] = Field(default_factory=list)
    refresh_cadence: str
    privacy_classification: str  # AGGREGATE, K_ANONYMIZED, RESTRICTED_PII


class MetricCatalogResponse(BaseModel):
    metrics: List[MetricDefinitionItem] = Field(default_factory=list)
    total_metrics: int = 0


# ---------------------------------------------------------------------------
# Tourist Personal Trip Analytics
# ---------------------------------------------------------------------------

class TouristTripSummary(BaseModel):
    trip_id: str
    title: str
    status: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    distance_km: float = 0.0
    zones_visited_count: int = 0
    zones_visited_names: List[str] = Field(default_factory=list)
    total_dwell_seconds: float = 0.0
    tracking_coverage_percentage: Optional[float] = None
    gps_accuracy_avg_meters: Optional[float] = None
    anomaly_events_count: int = 0
    safety_events_count: int = 0
    incidents_count: int = 0
    sos_count: int = 0
    tracking_gaps_count: int = 0
    quality_status: QualityStatus = QualityStatus.GOOD


class TouristAnalyticsResponse(BaseModel):
    tourist_id: str
    total_trips: int = 0
    completed_trips: int = 0
    total_distance_km: float = 0.0
    total_duration_hours: float = 0.0
    unique_zones_visited: int = 0
    safety_events_summary: Dict[str, int] = Field(default_factory=dict)
    trips: List[TouristTripSummary] = Field(default_factory=list)
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


# ---------------------------------------------------------------------------
# Export Job Models
# ---------------------------------------------------------------------------

class ExportJobCreateRequest(BaseModel):
    export_type: str = Field(description="incidents, zones, responders, safety, telemetry, escalations, hotspots")
    format: ExportFormat = ExportFormat.CSV
    filters: Optional[AnalyticsFilterParams] = None


class ExportJobResponse(BaseModel):
    job_id: str
    requested_by: str
    export_type: str
    format: ExportFormat
    status: ExportStatus
    created_at: str
    completed_at: Optional[str] = None
    file_reference: Optional[str] = None
    record_count: int = 0
    file_size_bytes: Optional[int] = None
    download_url: Optional[str] = None
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Audit Log Models
# ---------------------------------------------------------------------------

class AnalyticsAuditLogEntry(BaseModel):
    id: str
    action: str  # "EXPORT_DATA", "QUERY_FORECAST", "ACK_ALERT", "CONFIG_CHANGE"
    user_id: str
    role: str
    jurisdiction_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str
