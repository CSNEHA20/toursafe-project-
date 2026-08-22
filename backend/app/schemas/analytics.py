"""
TourSafe Analytics Domain Schemas and Models

Pydantic v2 schemas defining analytical requests, filters, time-bucketing,
operational KPIs, zone intelligence, incident metrics, safety state analysis,
anomaly conversion, responder operational statistics, notification health,
data quality scoring, heatmaps, and export job models.
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


class HeatmapMetricType(str, Enum):
    TOURIST_DENSITY = "tourist_density"
    ZONE_VISITS = "zone_visits"
    INCIDENTS = "incidents"
    SOS_EVENTS = "sos_events"
    ANOMALIES = "anomalies"
    RESPONSE_ACTIVITY = "response_activity"


class QualityStatus(str, Enum):
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    POOR = "POOR"
    UNKNOWN = "UNKNOWN"


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
    timezone: Optional[str] = Field(
        default="UTC",
        description="Client timezone for presentation (e.g. UTC, Asia/Kolkata)"
    )
    granularity: TimeGranularity = Field(
        default=TimeGranularity.DAY,
        description="Time aggregation granularity"
    )
    zone_id: Optional[str] = None
    risk_level: Optional[str] = None
    incident_source: Optional[str] = None
    severity: Optional[str] = None
    model_version: Optional[str] = None
    responder_id: Optional[str] = None
    unit_id: Optional[str] = None
    bypass_cache: bool = Field(default=False, description="Force fresh aggregation bypass")


# ---------------------------------------------------------------------------
# Freshness & Metadata Models
# ---------------------------------------------------------------------------

class DataFreshnessMeta(BaseModel):
    data_updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data_range_start: Optional[str] = None
    data_range_end: Optional[str] = None
    freshness_seconds: float = 0.0
    aggregation_level: str = "canonical_db"
    is_cached: bool = False
    sample_size: int = 0
    data_status: str = "REAL_DATA"  # REAL_DATA, PARTIAL_DATA, INSUFFICIENT_DATA, UNKNOWN


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
# Operational Overview & KPIs
# ---------------------------------------------------------------------------

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
    tracking_coverage_percentage: Optional[float] = None  # None if expected duration undefined
    gps_availability_percentage: float = 0.0
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)
    incident_trend: List[TimeSeriesPoint] = Field(default_factory=list)
    safety_state_distribution: Dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Incident Analytics
# ---------------------------------------------------------------------------

class IncidentDurationMetrics(BaseModel):
    count: int = 0
    p50_seconds: Optional[float] = None
    p90_seconds: Optional[float] = None
    p95_seconds: Optional[float] = None
    mean_seconds: Optional[float] = None
    min_seconds: Optional[float] = None
    max_seconds: Optional[float] = None


class IncidentAnalyticsResponse(BaseModel):
    total_incidents: int = 0
    open_incidents: int = 0
    resolved_incidents: int = 0
    closed_incidents: int = 0
    cancelled_incidents: int = 0
    escalated_incidents: int = 0
    false_alarms: int = 0
    false_alarm_rate: float = 0.0
    by_source: Dict[str, int] = Field(default_factory=dict)  # MANUAL_SOS, SAFETY_ENGINE, AUTHORITY_CREATED
    by_severity: Dict[str, int] = Field(default_factory=dict)  # LOW, MEDIUM, HIGH, CRITICAL
    by_zone: Dict[str, int] = Field(default_factory=dict)
    time_to_acknowledge: IncidentDurationMetrics = Field(default_factory=IncidentDurationMetrics)
    time_to_assign: IncidentDurationMetrics = Field(default_factory=IncidentDurationMetrics)
    time_to_response: IncidentDurationMetrics = Field(default_factory=IncidentDurationMetrics)
    time_to_arrival: IncidentDurationMetrics = Field(default_factory=IncidentDurationMetrics)
    time_to_resolution: IncidentDurationMetrics = Field(default_factory=IncidentDurationMetrics)
    time_to_close: IncidentDurationMetrics = Field(default_factory=IncidentDurationMetrics)
    sla_threshold_seconds: Optional[float] = 900.0  # 15 minutes default target
    within_sla_count: int = 0
    outside_sla_count: int = 0
    sla_compliance_rate: Optional[float] = None
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


# ---------------------------------------------------------------------------
# Zone Analytics & Heatmaps
# ---------------------------------------------------------------------------

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
    active_tourists_now: int = 0


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


# ---------------------------------------------------------------------------
# Anomaly & Safety State Analytics
# ---------------------------------------------------------------------------

class AnomalyAnalyticsResponse(BaseModel):
    total_anomalies: int = 0
    active_anomalies: int = 0
    cleared_anomalies: int = 0
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
    inference_latency_avg_ms: Optional[float] = None
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


class SafetyStateAnalyticsResponse(BaseModel):
    total_decisions: int = 0
    state_durations_seconds: Dict[str, float] = Field(default_factory=dict)
    state_counts: Dict[str, int] = Field(default_factory=dict)
    transition_frequencies: Dict[str, int] = Field(default_factory=dict)
    unknown_state_causes: Dict[str, int] = Field(default_factory=dict)
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


# ---------------------------------------------------------------------------
# Responder & Unit Analytics
# ---------------------------------------------------------------------------

class ResponderAnalyticsResponse(BaseModel):
    total_responders: int = 0
    active_responders: int = 0
    available_responders: int = 0
    assigned_responders: int = 0
    offline_responders: int = 0
    total_assignments: int = 0
    completed_assignments: int = 0
    rejected_assignments: int = 0
    rejection_rate: float = 0.0
    acceptance_rate: float = 0.0
    p50_response_time_seconds: Optional[float] = None
    p90_response_time_seconds: Optional[float] = None
    p50_arrival_time_seconds: Optional[float] = None
    p90_arrival_time_seconds: Optional[float] = None
    assignments_by_responder_type: Dict[str, int] = Field(default_factory=dict)
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
# Data Quality Dashboard
# ---------------------------------------------------------------------------

class QualityDomainMetric(BaseModel):
    domain: str
    status: QualityStatus
    score: float  # 0.0 to 100.0
    details: Dict[str, Any] = Field(default_factory=dict)
    evaluated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DataQualityDashboardResponse(BaseModel):
    overall_health: QualityStatus
    gps_quality: QualityDomainMetric
    telemetry_quality: QualityDomainMetric
    ml_inference_quality: QualityDomainMetric
    zone_geometry_validity: QualityDomainMetric
    incident_completeness: QualityDomainMetric
    notification_delivery_health: QualityDomainMetric
    freshness: DataFreshnessMeta = Field(default_factory=DataFreshnessMeta)


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
    export_type: str = Field(description="incidents, zones, responders, safety, telemetry")
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
