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
    SECURITY = "SECURITY"


class ResponderStatus(str, Enum):
    OFFLINE = "OFFLINE"
    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    RESPONDING = "RESPONDING"
    ON_SCENE = "ON_SCENE"
    UNAVAILABLE = "UNAVAILABLE"


class UnitStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    RESPONDING = "RESPONDING"
    ON_SCENE = "ON_SCENE"
    UNAVAILABLE = "UNAVAILABLE"
    OFFLINE = "OFFLINE"
    MAINTENANCE = "MAINTENANCE"


class AssignmentStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class RejectionReason(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    WRONG_CAPABILITY = "WRONG_CAPABILITY"
    ALREADY_RESPONDING = "ALREADY_RESPONDING"
    OTHER = "OTHER"


class ResponderCapability(str, Enum):
    MEDICAL = "MEDICAL"
    FIRST_AID = "FIRST_AID"
    SEARCH = "SEARCH"
    RESCUE = "RESCUE"
    SECURITY = "SECURITY"
    TRANSPORT = "TRANSPORT"
    FIRE_RESPONSE = "FIRE_RESPONSE"
    CROWD_CONTROL = "CROWD_CONTROL"
    WATER_RESCUE = "WATER_RESCUE"


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
    user_id: Optional[str] = None
    name: str
    type: ResponderType = ResponderType.FIELD_RESPONDER
    unit_id: Optional[str] = None
    status: ResponderStatus = ResponderStatus.AVAILABLE
    capabilities: List[str] = Field(default_factory=list)
    current_location: Optional[Dict[str, Any]] = None  # None if unavailable
    contact_channel: Optional[str] = None
    contact_phone: Optional[str] = None
    active: bool = True
    assigned_incident_id: Optional[str] = None
    active_assignment_id: Optional[str] = None
    tracking_session_id: Optional[str] = None
    tracking_active: bool = False
    last_location_timestamp: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ResponderUnitRecord(BaseModel):
    unit_id: str = Field(default_factory=lambda: f"unit_{uuid.uuid4().hex[:10]}")
    name: str
    type: ResponderType = ResponderType.FIELD_RESPONDER
    status: UnitStatus = UnitStatus.AVAILABLE
    members: List[str] = Field(default_factory=list)  # list of responder_ids
    capabilities: List[str] = Field(default_factory=list)
    current_location: Optional[Dict[str, Any]] = None
    base_location: Optional[Dict[str, Any]] = None
    active_incident_id: Optional[str] = None
    active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AssignmentRecord(BaseModel):
    assignment_id: str = Field(default_factory=lambda: f"asgn_{uuid.uuid4().hex[:12]}")
    incident_id: str
    responder_id: str
    unit_id: Optional[str] = None
    assigned_by: str
    assigned_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    accepted_at: Optional[str] = None
    rejected_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    started_at: Optional[str] = None
    arrived_at: Optional[str] = None
    arrival_location: Optional[Dict[str, Any]] = None
    arrival_accuracy: Optional[float] = None
    completed_at: Optional[str] = None
    completion_reason: Optional[str] = None
    completion_notes: Optional[str] = None
    cancelled_at: Optional[str] = None
    cancellation_reason: Optional[str] = None
    status: AssignmentStatus = AssignmentStatus.PENDING
    notes: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OperationalMessageRecord(BaseModel):
    message_id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    incident_id: str
    assignment_id: Optional[str] = None
    sender_id: str
    sender_type: str  # "RESPONDER", "AUTHORITY", "SYSTEM"
    sender_name: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    content: str
    delivery_status: str = "DELIVERED"
    read_at: Optional[str] = None


class NotificationRecord(BaseModel):
    notification_id: str = Field(default_factory=lambda: f"notif_{uuid.uuid4().hex[:12]}")
    incident_id: Optional[str] = None
    recipient: str
    recipient_type: str = "EMERGENCY_CONTACT"  # AUTHORITY_CENTER, EMERGENCY_CONTACT, TOURIST, RESPONDER
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
# Authority & Responder Action Requests
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
    user_id: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    contact_channel: Optional[str] = None
    contact_phone: Optional[str] = None


class ResponderUpdateRequest(BaseModel):
    status: Optional[ResponderStatus] = None
    capabilities: Optional[List[str]] = None
    current_location: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None
    unit_id: Optional[str] = None
    contact_phone: Optional[str] = None


class ResponderStatusUpdateRequest(BaseModel):
    status: ResponderStatus
    reason: Optional[str] = None


class ResponderLocationUpdateRequest(BaseModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    heading: Optional[float] = None
    speed: Optional[float] = None
    altitude: Optional[float] = None
    timestamp: Optional[str] = None
    tracking_session_id: Optional[str] = None


class AssignmentAcceptRequest(BaseModel):
    notes: Optional[str] = None


class AssignmentRejectRequest(BaseModel):
    reason: RejectionReason = RejectionReason.UNAVAILABLE
    details: Optional[str] = None


class AssignmentArrivedRequest(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy: Optional[float] = None
    notes: Optional[str] = None
    force_override: bool = False  # Controlled fallback if GPS unavailable or degraded


class AssignmentCompleteRequest(BaseModel):
    completion_reason: str = Field(..., min_length=3)
    resolution_notes: Optional[str] = None


class ResponderUnitCreateRequest(BaseModel):
    name: str
    type: ResponderType = ResponderType.FIELD_RESPONDER
    capabilities: List[str] = Field(default_factory=list)
    members: List[str] = Field(default_factory=list)
    base_location: Optional[Dict[str, Any]] = None


class ResponderUnitUpdateRequest(BaseModel):
    name: Optional[str] = None
    status: Optional[UnitStatus] = None
    capabilities: Optional[List[str]] = None
    members: Optional[List[str]] = None
    base_location: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None


class OperationalMessageCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)
    assignment_id: Optional[str] = None


class ResponderSelfProfileResponse(BaseModel):
    profile: ResponderRecord
    unit: Optional[ResponderUnitRecord] = None
    active_assignment: Optional[AssignmentRecord] = None
    tracking_active: bool = False
    last_location: Optional[Dict[str, Any]] = None
    location_freshness: str = "UNKNOWN"  # LIVE, RECENT, STALE, OFFLINE


class ResponderRecommendationItem(BaseModel):
    responder_id: str
    name: str
    type: ResponderType
    unit_id: Optional[str] = None
    unit_name: Optional[str] = None
    status: ResponderStatus
    capabilities: List[str]
    matched_capabilities: List[str]
    distance_meters: Optional[float] = None
    location_freshness: str = "UNKNOWN"
    current_location: Optional[Dict[str, Any]] = None
    active_assignment_id: Optional[str] = None
    score: float = 0.0


class HandoverReason(str, Enum):
    MEDICAL = "MEDICAL"
    CAPABILITY = "CAPABILITY"
    LOCATION = "LOCATION"
    SHIFT = "SHIFT"
    UNAVAILABLE = "UNAVAILABLE"
    OTHER = "OTHER"


class AssignmentHandoverRequest(BaseModel):
    reason: HandoverReason = HandoverReason.OTHER
    details: Optional[str] = None
    replacement_capability: Optional[str] = None


class SceneAssessmentCategory(str, Enum):
    TOURIST_SAFE = "TOURIST_SAFE"
    MEDICAL_ASSISTANCE = "MEDICAL_ASSISTANCE"
    SECURITY_ASSISTANCE = "SECURITY_ASSISTANCE"
    LOCATION_ISSUE = "LOCATION_ISSUE"
    FALSE_ALARM = "FALSE_ALARM"
    UNABLE_TO_LOCATE = "UNABLE_TO_LOCATE"
    OTHER = "OTHER"


class SceneAssessmentRequest(BaseModel):
    category: SceneAssessmentCategory
    notes: Optional[str] = None
    tourist_status_observed: Optional[str] = None
    follow_up_required: bool = False
    evidence_metadata: Dict[str, Any] = Field(default_factory=dict)


class OfflineFieldNoteItem(BaseModel):
    client_note_id: str
    incident_id: str
    content: str
    recorded_at: str
    author_id: Optional[str] = None
    author_role: str = "responder"
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class FieldNotesBatchSyncRequest(BaseModel):
    notes: List[OfflineFieldNoteItem] = Field(default_factory=list)


class FieldNotesBatchSyncResponse(BaseModel):
    synced_count: int
    synced_ids: List[str]
    failed_ids: List[str] = Field(default_factory=list)
    timestamp: str


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


# ---------------------------------------------------------------------------
# Incident Communication & Multi-Party Coordination Schemas (Prompt 22)
# ---------------------------------------------------------------------------

class ChannelStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RESTRICTED = "RESTRICTED"
    CLOSED = "CLOSED"


class ParticipantRole(str, Enum):
    TOURIST = "TOURIST"
    AUTHORITY = "AUTHORITY"
    RESPONDER = "RESPONDER"
    SUPERVISOR = "SUPERVISOR"
    SYSTEM = "SYSTEM"


class ParticipantStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RESTRICTED = "RESTRICTED"
    REMOVED = "REMOVED"


class ResponderAssignmentRole(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    SPECIALIST = "SPECIALIST"
    SUPPORT = "SUPPORT"
    NONE = "NONE"


class MessagePriority(str, Enum):
    NORMAL = "NORMAL"
    IMPORTANT = "IMPORTANT"
    CRITICAL = "CRITICAL"


class MessageType(str, Enum):
    TEXT = "TEXT"
    SYSTEM = "SYSTEM"
    OPERATIONAL = "OPERATIONAL"
    LOCATION = "LOCATION"
    STATUS = "STATUS"
    ATTACHMENT_REFERENCE = "ATTACHMENT_REFERENCE"


class MessageDeliveryStatus(str, Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


class ParticipantPresenceStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    RECONNECTING = "RECONNECTING"


class StructuredLocationData(BaseModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    altitude: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    label: Optional[str] = None
    expires_at: Optional[str] = None


class AttachmentMetadataRecord(BaseModel):
    attachment_id: str = Field(default_factory=lambda: f"att_{uuid.uuid4().hex[:12]}")
    file_name: str
    mime_type: str
    size_bytes: int
    url: str
    sha256_hash: Optional[str] = None
    is_formal_evidence: bool = False
    uploaded_by: str
    uploaded_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MessageAcknowledgementRecord(BaseModel):
    actor_id: str
    actor_role: str
    actor_name: Optional[str] = None
    acknowledged_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: Optional[str] = None


class IncidentMessageRecord(BaseModel):
    message_id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    channel_id: str
    incident_id: str
    sender_id: str
    sender_role: ParticipantRole
    sender_name: Optional[str] = None
    message_type: MessageType = MessageType.TEXT
    priority: MessagePriority = MessagePriority.NORMAL
    content: str
    location_data: Optional[StructuredLocationData] = None
    attachment_data: Optional[AttachmentMetadataRecord] = None
    client_message_id: Optional[str] = None
    server_sequence: int = 0
    delivery_status: MessageDeliveryStatus = MessageDeliveryStatus.DELIVERED
    requires_acknowledgement: bool = False
    read_by: Dict[str, str] = Field(default_factory=dict)  # user_id -> read_at iso
    acknowledged_by: List[MessageAcknowledgementRecord] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    deleted_at: Optional[str] = None


class ChannelParticipantRecord(BaseModel):
    participant_id: str = Field(default_factory=lambda: f"prt_{uuid.uuid4().hex[:10]}")
    channel_id: str
    incident_id: str
    user_id: str
    display_name: str
    role: ParticipantRole
    responder_role: ResponderAssignmentRole = ResponderAssignmentRole.NONE
    status: ParticipantStatus = ParticipantStatus.ACTIVE
    presence: ParticipantPresenceStatus = ParticipantPresenceStatus.OFFLINE
    last_seen_at: Optional[str] = None
    last_read_sequence: int = 0
    last_read_at: Optional[str] = None
    joined_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    left_at: Optional[str] = None
    permissions: List[str] = Field(default_factory=lambda: [
        "SEND_MESSAGE",
        "SEND_OPERATIONAL",
        "SEND_LOCATION",
        "SEND_ATTACHMENT",
        "ACKNOWLEDGE_MESSAGES",
    ])


class IncidentChannelRecord(BaseModel):
    channel_id: str = Field(default_factory=lambda: f"chn_{uuid.uuid4().hex[:12]}")
    incident_id: str
    status: ChannelStatus = ChannelStatus.ACTIVE
    sequence_counter: int = 0
    version: int = 1
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    closed_at: Optional[str] = None
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MessageSendRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    client_message_id: Optional[str] = None
    message_type: MessageType = MessageType.TEXT
    priority: MessagePriority = MessagePriority.NORMAL
    requires_acknowledgement: bool = False
    location_data: Optional[StructuredLocationData] = None
    attachment_data: Optional[AttachmentMetadataRecord] = None


class MessageAckRequest(BaseModel):
    notes: Optional[str] = None


class ChannelParticipantAddRequest(BaseModel):
    user_id: str
    display_name: str
    role: ParticipantRole
    responder_role: ResponderAssignmentRole = ResponderAssignmentRole.NONE
    permissions: Optional[List[str]] = None


class ChannelParticipantUpdateRequest(BaseModel):
    status: Optional[ParticipantStatus] = None
    responder_role: Optional[ResponderAssignmentRole] = None
    permissions: Optional[List[str]] = None


class ChannelSnapshotResponse(BaseModel):
    channel: IncidentChannelRecord
    participants: List[ChannelParticipantRecord]
    messages: List[IncidentMessageRecord]
    last_sequence: int
    unread_count: int = 0
    pending_acknowledgements_count: int = 0


class MessageGapRecoveryResponse(BaseModel):
    channel_id: str
    incident_id: str
    since_sequence: int
    current_sequence: int
    messages: List[IncidentMessageRecord]


class AttachmentUploadRequest(BaseModel):
    file_name: str
    mime_type: str
    size_bytes: int
    is_formal_evidence: bool = False
    sha256_hash: Optional[str] = None


class AttachmentUploadResponse(BaseModel):
    attachment: AttachmentMetadataRecord
    upload_url: str
    download_token: str


class MultiResponderAssignRequest(BaseModel):
    responder_id: str
    assignment_role: ResponderAssignmentRole = ResponderAssignmentRole.SECONDARY
    unit_id: Optional[str] = None
    notes: Optional[str] = None


class MessageSearchResponse(BaseModel):
    incident_id: str
    query: str
    total: int
    messages: List[IncidentMessageRecord]


