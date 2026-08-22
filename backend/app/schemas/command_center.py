"""
TourSafe Authority Command Center & Live Operations Schemas
Defines structured data contracts for operational snapshots, live entities,
system diagnostics, search, and KPI aggregation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StalenessStatus(str, Enum):
    LIVE = "LIVE"          # Updated within 30s
    RECENT = "RECENT"      # Updated within 2m
    STALE = "STALE"        # Updated within 10m
    UNKNOWN = "UNKNOWN"    # >10m or no data


class SubsystemHealth(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


class TouristLiveSummary(BaseModel):
    tourist_id: str
    user_id: Optional[str] = None
    full_name: str = "Anonymous Tourist"
    phone: Optional[str] = None
    nationality: Optional[str] = None
    safety_state: str = "NORMAL"
    tracking_status: str = "active"
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy_m: Optional[float] = None
    speed_mps: Optional[float] = None
    heading_deg: Optional[float] = None
    battery_pct: Optional[int] = None
    current_zone_id: Optional[str] = None
    current_zone_name: Optional[str] = None
    active_incident_id: Optional[str] = None
    last_updated_at: str
    staleness: StalenessStatus = StalenessStatus.LIVE
    verification_status: str = "verified"
    credential_status: str = "active"


class IncidentLiveSummary(BaseModel):
    incident_id: str
    tourist_id: str
    tourist_name: Optional[str] = "Tourist"
    source: str = "SAFETY_ENGINE"
    severity: str = "HIGH"
    status: str = "OPEN"
    started_at: str
    created_at: str
    updated_at: str
    age_seconds: int = 0
    assigned_responder_id: Optional[str] = None
    assigned_responder_name: Optional[str] = None
    assigned_unit_id: Optional[str] = None
    assigned_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    reasons: List[str] = Field(default_factory=list)
    signal_summary: Dict[str, Any] = Field(default_factory=dict)
    timeline_summary: List[Dict[str, Any]] = Field(default_factory=list)
    version: int = 1
    is_sos: bool = False


class ResponderLiveSummary(BaseModel):
    responder_id: str
    user_id: Optional[str] = None
    full_name: str
    unit_id: Optional[str] = None
    unit_name: Optional[str] = None
    unit_type: str = "POLICE"
    status: str = "AVAILABLE"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    heading: Optional[float] = None
    speed: Optional[float] = None
    accuracy: Optional[float] = None
    battery_pct: Optional[int] = None
    current_assignment_id: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    organization_id: Optional[str] = None
    last_location_time: Optional[str] = None
    staleness: StalenessStatus = StalenessStatus.LIVE


class ZoneLiveSummary(BaseModel):
    zone_id: str
    name: str
    description: Optional[str] = None
    zone_type: str = "danger"
    risk_level: str = "critical"
    status: str = "active"
    is_active: bool = True
    center_lat: float
    center_lng: float
    boundary: Optional[Dict[str, Any]] = None
    center: Optional[Dict[str, Any]] = None
    active_tourists_count: int = 0
    active_incidents_count: int = 0
    recent_events_count: int = 0


class CommandCenterKpis(BaseModel):
    active_tourists: int = 0
    open_incidents: int = 0
    sos_incidents: int = 0
    active_responders: int = 0
    unassigned_incidents: int = 0
    elevated_safety_states: int = 0
    stale_tracking_tourists: int = 0


class SystemHealthStatus(BaseModel):
    realtime: SubsystemHealth = SubsystemHealth.HEALTHY
    telemetry: SubsystemHealth = SubsystemHealth.HEALTHY
    ml: SubsystemHealth = SubsystemHealth.HEALTHY
    notifications: SubsystemHealth = SubsystemHealth.HEALTHY
    map: SubsystemHealth = SubsystemHealth.HEALTHY
    backend: SubsystemHealth = SubsystemHealth.HEALTHY
    details: Dict[str, Any] = Field(default_factory=dict)
    checked_at: str


class AuthorityScope(BaseModel):
    authority_id: str
    user_id: str
    full_name: str
    organization_name: Optional[str] = None
    designation: Optional[str] = None
    role: str = "authority"
    jurisdiction_code: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)


class CommandCenterSnapshot(BaseModel):
    snapshot_id: str
    server_time: str
    authority_scope: AuthorityScope
    kpis: CommandCenterKpis
    system_health: SystemHealthStatus
    active_incidents: List[IncidentLiveSummary] = Field(default_factory=list)
    sos_queue: List[IncidentLiveSummary] = Field(default_factory=list)
    tourists: List[TouristLiveSummary] = Field(default_factory=list)
    responders: List[ResponderLiveSummary] = Field(default_factory=list)
    zones: List[ZoneLiveSummary] = Field(default_factory=list)
    freshness: Dict[str, Any] = Field(default_factory=dict)


class SearchResultItem(BaseModel):
    id: str
    entity_type: str  # "incident", "tourist", "responder", "zone", "credential"
    title: str
    subtitle: Optional[str] = None
    badge: Optional[str] = None
    status: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CommandCenterSearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem] = Field(default_factory=list)
    total_count: int = 0
