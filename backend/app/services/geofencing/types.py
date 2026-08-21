"""
TourSafe - Geofencing Domain Types & Data Contracts

Defines canonical enums, models, and payloads for:
- Zone membership states (OUTSIDE, ENTER_CANDIDATE, INSIDE, EXIT_CANDIDATE, UNCERTAIN, STALE)
- Membership confidence (HIGH, MEDIUM, LOW, UNCERTAIN)
- Containment evaluation results
- Active zone memberships in Redis
- Persistent zone transitions in MongoDB
- Realtime event contracts
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class ZoneMembershipState(str, Enum):
    """
    Formal state machine states for tourist zone membership.
    Prevents boundary jitter from creating spurious enter/exit events.
    """
    OUTSIDE = "outside"
    ENTER_CANDIDATE = "enter_candidate"
    INSIDE = "inside"
    EXIT_CANDIDATE = "exit_candidate"
    UNCERTAIN = "uncertain"
    STALE = "stale"


class MembershipConfidence(str, Enum):
    """
    Confidence classification based on GPS accuracy vs boundary distance.
    """
    HIGH = "high"          # Accuracy radius well within boundary (accuracy < distance/2)
    MEDIUM = "medium"      # Accuracy radius within boundary (accuracy <= distance)
    LOW = "low"            # Accuracy radius overlaps boundary (accuracy > distance)
    UNCERTAIN = "uncertain" # Accuracy extremely degraded (>50m) or point exactly on boundary


class ContainmentStatus(str, Enum):
    INSIDE = "inside"
    OUTSIDE = "outside"
    BOUNDARY = "boundary"
    UNCERTAIN = "uncertain"


class ContainmentResult(BaseModel):
    """
    Result of evaluating a GPS coordinate against a GeoJSON zone boundary.
    """
    is_contained: bool
    is_boundary: bool = False
    distance_to_boundary_meters: float
    accuracy_meters: float
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    confidence_level: MembershipConfidence
    containment_status: ContainmentStatus


class ActiveZoneMembership(BaseModel):
    """
    Real-time active zone membership record stored in Redis.
    Key: toursafe:geofence:active:{tourist_id}
    """
    zone_id: str
    name: str
    zone_type: str  # safe, warning, restricted
    risk_level: str  # low, medium, high, critical
    state: ZoneMembershipState
    confidence_level: MembershipConfidence
    confidence_score: float
    entered_at: str  # ISO8601 UTC
    last_seen_inside: str  # ISO8601 UTC
    dwell_duration_seconds: float = 0.0
    dwell_threshold_notified: bool = False
    last_location_timestamp: str
    distance_to_boundary_meters: float
    accuracy_meters: float
    geometry_version: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True, "populate_by_name": True}


class TouristGeofenceSnapshot(BaseModel):
    """
    Aggregated geofence snapshot for a tourist across all active zones.
    """
    tourist_id: str
    active_zones: List[ActiveZoneMembership] = Field(default_factory=list)
    highest_risk_level: str = "low"  # low, medium, high, critical
    primary_zone_type: str = "safe"   # safe, warning, restricted
    is_stale: bool = False
    last_gps_timestamp: Optional[str] = None
    total_active_zones: int = 0
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    model_config = {"use_enum_values": True, "populate_by_name": True}


class ZoneTransitionRecord(BaseModel):
    """
    Persistent document in MongoDB 'zone_transitions' collection.
    Tracks every confirmed zone transition and significant event for auditability.
    """
    id: str = Field(default_factory=lambda: f"ztr_{uuid.uuid4().hex[:12]}")
    transition_id: str = Field(default_factory=lambda: f"ztr_{uuid.uuid4().hex[:12]}")
    tourist_id: str
    user_id: str
    zone_id: str
    zone_name: str
    zone_type: str
    risk_level: str
    session_id: Optional[str] = None
    event_type: str  # zone.entered, zone.exited, zone.dwell.threshold_reached, zone.membership.uncertain, zone.membership.stale
    from_state: str
    to_state: str
    timestamp: str  # ISO8601 UTC of GPS sample
    latitude: float
    longitude: float
    location: Dict[str, Any]  # GeoJSON Point {"type": "Point", "coordinates": [lon, lat]}
    accuracy: float
    confidence_score: float
    confidence_level: str
    boundary_distance_meters: float
    dwell_duration_seconds: Optional[float] = None
    geometry_version: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    model_config = {"use_enum_values": True, "populate_by_name": True}


class GeofenceDiagnostics(BaseModel):
    """
    Development diagnostics payload for live geofencing inspection.
    """
    tourist_id: str
    current_coordinates: Dict[str, float]  # latitude, longitude
    gps_accuracy_meters: float
    gps_timestamp: str
    gps_freshness_seconds: Optional[float] = None
    candidate_zones_count: int
    candidate_zones: List[Dict[str, Any]]
    active_memberships: List[ActiveZoneMembership]
    highest_risk_level: str
    last_transition_event: Optional[Dict[str, Any]] = None
    processing_latency_ms: float
    engine_status: str = "operational"
