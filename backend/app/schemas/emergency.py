import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

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


class ResolutionCategory(str, Enum):
    TOURIST_SAFE = "TOURIST_SAFE"
    RESPONDER_ASSISTED = "RESPONDER_ASSISTED"
    FALSE_ALARM = "FALSE_ALARM"
    DUPLICATE = "DUPLICATE"
    TRANSFERRED = "TRANSFERRED"
    OTHER = "OTHER"


class ResponderType(str, Enum):
    AUTHORITY_OPERATOR = "AUTHORITY_OPERATOR"
    FIELD_RESPONDER = "FIELD_RESPONDER"
    POLICE = "POLICE"
    MEDICAL = "MEDICAL"
    FIRE = "FIRE"
    SEARCH_AND_RESCUE = "SEARCH_AND_RESCUE"


class ResponderStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    RESPONDING = "RESPONDING"
    UNAVAILABLE = "UNAVAILABLE"
    OFFLINE = "OFFLINE"


class NotificationChannel(str, Enum):
    PUSH = "PUSH"
    SMS = "SMS"
    EMAIL = "EMAIL"
    VOICE = "VOICE"


class NotificationStatus(str, Enum):
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Sub-Models & Records
# ---------------------------------------------------------------------------

class LocationSnapshot(BaseModel):
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None
    speed: Optional[float] = None
    timestamp: str
    location_status: str = "CURRENT"  # CURRENT, STALE, NO_GPS
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    zone_risk: Optional[str] = None


class TimelineEventRecord(BaseModel):
    event_id: str = Field(default_factory=lambda: f"tle_{uuid.uuid4().hex[:12]}")
    incident_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    actor_type: str  # TOURIST, AUTHORITY, SYSTEM, RESPONDER
    actor_id: str
    action: str  # e.g., "incident.created", "incident.acknowledged", "incident.assigned"
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    reason: Optional[str] = None


class IncidentNoteRecord(BaseModel):
    note_id: str = Field(default_factory=lambda: f"not_{uuid.uuid4().hex[:12]}")
    incident_id: str
    author_id: str
    author_role: str = "authority"
    author_name: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    content: str


class ResponderRecord(BaseModel):
    responder_id: str = Field(default_factory=lambda: f"resp_{uuid.uuid4().hex[:10]}")
    name: str
    type: ResponderType = ResponderType.FIELD_RESPONDER
    unit_id: Optional[str] = None
    status: ResponderStatus = ResponderStatus.AVAILABLE
    capabilities: List[str] = Field(default_factory=list)
    current_location: Optional[Dict[str, Any]] = None  # None if unavailable
    contact_channel: Optional[str] = None
    active: bool = True
    assigned_incident_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class NotificationRecord(BaseModel):
    notification_id: str = Field(default_factory=lambda: f"notif_{uuid.uuid4().hex[:12]}")
    incident_id: Optional[str] = None
    recipient: str
    recipient_type: str = "EMERGENCY_CONTACT"  # AUTHORITY_CENTER, EMERGENCY_CONTACT, TOURIST
    channel: NotificationChannel
    provider: str
    status: NotificationStatus = NotificationStatus.QUEUED
    payload: Dict[str, Any] = Field(default_factory=dict)
    policy_trigger: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sent_at: Optional[str] = None
    delivered_at: Optional[str] = None
    failed_at: Optional[str] = None
    error_code: Optional[str] = None


# ---------------------------------------------------------------------------
# SOS Requests & Responses
# ---------------------------------------------------------------------------

class SOSRequest(BaseModel):
    client_request_id: str = Field(..., description="Client idempotency key to prevent duplicate SOS on retry")
    session_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy: Optional[float] = None
    reason: Optional[str] = "Manual SOS initiated by tourist"
    category: Optional[str] = "GENERAL_EMERGENCY"
    timestamp: Optional[str] = None


class SOSResponse(BaseModel):
    sos_id: str
    incident_id: str
    status: str
    created_at: str
    tourist_id: str
    location_status: str
    location: Optional[LocationSnapshot] = None
    acknowledged: bool = False
    message: str


class SOSCancelRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="Mandatory reason for cancelling SOS")


# ---------------------------------------------------------------------------
# Authority Action Requests
# ---------------------------------------------------------------------------

class IncidentAcknowledgeRequest(BaseModel):
    notes: Optional[str] = None
    version: Optional[int] = None


class IncidentAssessRequest(BaseModel):
    severity: Optional[IncidentSeverity] = None
    notes: Optional[str] = None
    version: Optional[int] = None


class IncidentAssignRequest(BaseModel):
    responder_id: str
    unit_id: Optional[str] = None
    notes: Optional[str] = None
    version: Optional[int] = None


class IncidentResponseStartRequest(BaseModel):
    notes: Optional[str] = None
    estimated_arrival_minutes: Optional[int] = None
    version: Optional[int] = None


class IncidentEscalateRequest(BaseModel):
    reason: str = Field(..., min_length=3)
    target_severity: Optional[IncidentSeverity] = None
    notes: Optional[str] = None
    version: Optional[int] = None


class IncidentNoteCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)


class IncidentResolveRequest(BaseModel):
    resolution_reason: str = Field(..., min_length=3)
    resolution_category: ResolutionCategory = ResolutionCategory.TOURIST_SAFE
    notes: Optional[str] = None
    version: Optional[int] = None


class IncidentCancelRequest(BaseModel):
    cancellation_reason: str = Field(..., min_length=3)
    is_false_alarm: bool = False
    notes: Optional[str] = None
    version: Optional[int] = None


class IncidentCloseRequest(BaseModel):
    notes: Optional[str] = None
    version: Optional[int] = None


class ResponderCreateRequest(BaseModel):
    name: str
    type: ResponderType = ResponderType.FIELD_RESPONDER
    unit_id: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    contact_channel: Optional[str] = None


class ResponderUpdateRequest(BaseModel):
    status: Optional[ResponderStatus] = None
    capabilities: Optional[List[str]] = None
    current_location: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None
    unit_id: Optional[str] = None


class IncidentMetricsResponse(BaseModel):
    total_incidents: int
    open_incidents: int
    acknowledged_incidents: int
    responding_incidents: int
    escalated_incidents: int
    resolved_incidents: int
    closed_incidents: int
    cancelled_incidents: int
    avg_time_to_acknowledge_seconds: Optional[float] = None
    avg_time_to_assign_seconds: Optional[float] = None
    avg_time_to_resolve_seconds: Optional[float] = None
    escalation_count: int = 0
    false_alarm_rate: float = 0.0
    notification_stats: Dict[str, int] = Field(default_factory=dict)
