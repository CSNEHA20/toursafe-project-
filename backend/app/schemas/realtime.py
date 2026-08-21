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

    # AI Anomaly events
    ANOMALY_DETECTED = "anomaly.detected"
    ANOMALY_CONFIRMED = "anomaly.confirmed"
    ANOMALY_CLEARED = "anomaly.cleared"

    # Emergency events
    EMERGENCY_CREATED = "emergency.created"
    EMERGENCY_UPDATED = "emergency.updated"
    EMERGENCY_DISPATCHED = "emergency.dispatched"

    # Identity events
    IDENTITY_VERIFIED = "identity.verified"
    IDENTITY_ACCESS_GRANTED = "identity.access_granted"
    IDENTITY_ACCESS_REVOKED = "identity.access_revoked"

    # E-FIR events
    EFIR_CREATED = "efir.created"
    EFIR_UPDATED = "efir.updated"
    EFIR_DISPATCHED = "efir.dispatched"


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
