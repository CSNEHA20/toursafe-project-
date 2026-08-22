import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class RealtimeEventType(str, Enum):
    # System events
    SYSTEM_CONNECTED = "system.connected"
    SYSTEM_DISCONNECTED = "system.disconnected"
    SYSTEM_STATUS = "system.status"
    SYSTEM_HEARTBEAT = "system.heartbeat"
    SYSTEM_ERROR = "system.error"

    # Tourist events
    TOURIST_PROFILE_UPDATED = "tourist.profile.updated"
    TOURIST_STATUS_UPDATED = "tourist.status.updated"

    # Location events
    LOCATION_UPDATED = "location.updated"
    LOCATION_STALE = "location.stale"

    # Zone events
    ZONE_CREATED = "zone.created"
    ZONE_UPDATED = "zone.updated"
    ZONE_STATUS_CHANGED = "zone.status_changed"
    ZONE_ENTERED = "zone.entered"
    ZONE_EXITED = "zone.exited"
    ZONE_DWELL_THRESHOLD_REACHED = "zone.dwell.threshold_reached"
    ZONE_MEMBERSHIP_UNCERTAIN = "zone.membership.uncertain"
    ZONE_MEMBERSHIP_STALE = "zone.membership.stale"

    # Alert events
    ALERT_CREATED = "alert.created"
    ALERT_UPDATED = "alert.updated"
    ALERT_RESOLVED = "alert.resolved"

    # SOS events
    SOS_CREATED = "sos.created"
    SOS_UPDATED = "sos.updated"
    SOS_RESOLVED = "sos.resolved"

    # Telemetry events
    TELEMETRY_STARTED = "telemetry.started"
    TELEMETRY_STOPPED = "telemetry.stopped"
    TELEMETRY_STATUS = "telemetry.status"
    TELEMETRY_SESSION_STARTED = "telemetry.session.started"
    TELEMETRY_SESSION_STOPPED = "telemetry.session.stopped"
    TELEMETRY_STATUS_UPDATED = "telemetry.status.updated"
    TELEMETRY_QUALITY_UPDATED = "telemetry.quality.updated"

    # AI Anomaly events
    ANOMALY_DETECTED = "anomaly.detected"
    ANOMALY_CONFIRMED = "anomaly.confirmed"
    ANOMALY_CLEARED = "anomaly.cleared"

    # Safety & Incident events
    SAFETY_STATE_CHANGED = "safety.state.changed"
    INCIDENT_CREATED = "incident.created"
    INCIDENT_UPDATED = "incident.updated"
    INCIDENT_ACKNOWLEDGED = "incident.acknowledged"
    INCIDENT_ASSESSING = "incident.assessing"
    INCIDENT_ASSIGNED = "incident.assigned"
    INCIDENT_RESPONSE_STARTED = "incident.response.started"
    INCIDENT_ESCALATED = "incident.escalated"
    INCIDENT_NOTE_ADDED = "incident.note.added"
    INCIDENT_LOCATION_UPDATED = "incident.location.updated"
    INCIDENT_SEVERITY_CHANGED = "incident.severity.changed"
    INCIDENT_RESOLVED = "incident.resolved"
    INCIDENT_CANCELLED = "incident.cancelled"
    INCIDENT_CLOSED = "incident.closed"

    # Emergency events
    EMERGENCY_CREATED = "emergency.created"
    EMERGENCY_UPDATED = "emergency.updated"
    EMERGENCY_DISPATCHED = "emergency.dispatched"

    # Responder events
    RESPONDER_STATUS_UPDATED = "responder.status.updated"
    RESPONDER_LOCATION_UPDATED = "responder.location.updated"
    RESPONDER_ASSIGNED = "responder.assigned"
    RESPONDER_ACCEPTED = "responder.accepted"
    RESPONDER_REJECTED = "responder.rejected"
    RESPONDER_RESPONSE_STARTED = "responder.response.started"
    RESPONDER_ARRIVED = "responder.arrived"
    RESPONDER_COMPLETED = "responder.completed"
    RESPONDER_MESSAGE_SENT = "responder.message.sent"
    RESPONDER_MESSAGE_RECEIVED = "responder.message.received"

    # Identity events
    IDENTITY_VERIFIED = "identity.verified"
    IDENTITY_ACCESS_GRANTED = "identity.access_granted"
    IDENTITY_ACCESS_REVOKED = "identity.access_revoked"

    # E-FIR events
    EFIR_CREATED = "efir.created"
    EFIR_UPDATED = "efir.updated"
    EFIR_DISPATCHED = "efir.dispatched"

    # Incident Channel & Communication events
    MESSAGE_CREATED = "message.created"
    MESSAGE_DELIVERED = "message.delivered"
    MESSAGE_READ = "message.read"
    MESSAGE_ACKNOWLEDGED = "message.acknowledged"
    PARTICIPANT_ADDED = "participant.added"
    PARTICIPANT_REMOVED = "participant.removed"
    PARTICIPANT_UPDATED = "participant.updated"
    PARTICIPANT_PRESENCE = "participant.presence"
    CHANNEL_UPDATED = "channel.updated"
    DISPATCH_CREATED = "dispatch.created"
    DISPATCH_ACCEPTED = "dispatch.accepted"
    DISPATCH_DECLINED = "dispatch.declined"
    DISPATCH_REASSIGNED = "dispatch.reassigned"
    HANDOVER_REQUESTED = "handover.requested"
    HANDOVER_COMPLETED = "handover.completed"


ALL_REGISTERED_EVENT_TYPES = {e.value for e in RealtimeEventType}


class RealtimeEventEnvelope(BaseModel):
    """
    Canonical Realtime Event Envelope (Version 1).
    Every message delivered across TourSafe realtime channels conforms strictly to this contract.
    """
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    event_type: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = Field(default="backend")
    version: int = Field(default=1)
    payload: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if not v or not isinstance(v, str) or "." not in v:
            raise ValueError(f"Invalid event_type format '{v}'. Expected category.action format.")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Event envelope version must be >= 1")
        return v


class ClientActionType(str, Enum):
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PING = "ping"
    TEST_EVENT = "test_event"


class ClientIncomingMessage(BaseModel):
    """Message sent from client over WebSocket connection."""
    action: ClientActionType
    channel: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class DevTestEventRequest(BaseModel):
    """Request payload for dev-only test event publisher."""
    event_type: str = Field(..., json_schema_extra={"example": "zone.updated"})
    channel: Optional[str] = Field(None, json_schema_extra={"example": "authority:operations"})
    target_user_id: Optional[str] = Field(None, json_schema_extra={"example": "user_123"})
    target_role: Optional[str] = Field(None, json_schema_extra={"example": "authority"})
    payload: Dict[str, Any] = Field(default_factory=dict)



class ConnectionStatsResponse(BaseModel):
    active_connections: int
    unique_users: int
    active_channels: int
    channels: List[str]
    roles_connected: Dict[str, int]
