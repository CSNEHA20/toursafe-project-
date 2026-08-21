from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
import uuid


class LocationStaleness(str, Enum):
    LIVE = "LIVE"          # <= 15s
    RECENT = "RECENT"      # <= 60s
    STALE = "STALE"        # <= 300s or Redis TTL expired
    UNKNOWN = "UNKNOWN"    # > 300s or no record


class TrackingSessionStatus(str, Enum):
    STARTING = "starting"
    ACTIVE = "active"
    PAUSED = "paused"
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"
    ERROR = "error"


class LocationSampleCreate(BaseModel):
    """
    Client-submitted Location Sample.
    Note: tourist_id and user_id are derived from JWT auth context and NOT trusted from body.
    """
    session_id: str = Field(..., description="ID of the active tracking session")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of GPS fix")
    latitude: float = Field(..., description="Latitude in degrees [-90, 90]")
    longitude: float = Field(..., description="Longitude in degrees [-180, 180]")
    altitude: Optional[float] = Field(None, description="Altitude in meters")
    accuracy: Optional[float] = Field(None, description="Horizontal accuracy in meters (>= 0)")
    speed: Optional[float] = Field(None, description="Speed in meters/second (>= 0)")
    heading: Optional[float] = Field(None, description="True heading in degrees [0, 360]")
    provider: Optional[str] = Field("gps", description="Location provider: gps, fused, network")
    is_background: bool = Field(False, description="Whether sample was recorded in background")
    sequence_number: int = Field(1, description="Monotonically increasing sequence number >= 1")
    network_status: Optional[str] = Field("online", description="Client connectivity state")
    device_id: Optional[str] = Field(None, description="Client device identifier")

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if v < -90.0 or v > 90.0:
            raise ValueError(f"Latitude {v} out of valid bounds [-90, 90]")
        return round(v, 7)

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if v < -180.0 or v > 180.0:
            raise ValueError(f"Longitude {v} out of valid bounds [-180, 180]")
        return round(v, 7)

    @field_validator("accuracy")
    @classmethod
    def validate_accuracy(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError(f"Accuracy {v} must be non-negative")
        return v

    @field_validator("speed")
    @classmethod
    def validate_speed(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError(f"Speed {v} must be non-negative")
        return v

    @field_validator("heading")
    @classmethod
    def validate_heading(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0.0 or v > 360.0):
            raise ValueError(f"Heading {v} must be within [0, 360]")
        return v

    @field_validator("sequence_number")
    @classmethod
    def validate_sequence_number(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Sequence number must be >= 1")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        try:
            # Verify ISO format parseability
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            # Disallow extreme future timestamps (> 10 minutes ahead of server clock)
            now = datetime.now(timezone.utc)
            if (parsed - now).total_seconds() > 600:
                raise ValueError("Timestamp is too far in the future")
        except ValueError as e:
            if "too far in the future" in str(e):
                raise
            raise ValueError(f"Invalid ISO 8601 timestamp string: '{v}'")
        return v


class LocationSampleResponse(BaseModel):
    location_id: str
    tourist_id: str
    session_id: str
    timestamp: str
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    provider: Optional[str] = "gps"
    is_background: bool = False
    sequence_number: int
    created_at: str


class LiveLocationPayload(BaseModel):
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    is_background: bool = False


class LiveLocationResponse(BaseModel):
    tourist_id: str
    location: Optional[LiveLocationPayload] = None
    timestamp: Optional[str] = None
    session_id: Optional[str] = None
    sequence_number: Optional[int] = None
    tracking_status: str = "stopped"
    staleness: LocationStaleness = LocationStaleness.UNKNOWN
    age_seconds: Optional[float] = None


class TrackingSessionStartRequest(BaseModel):
    device_id: Optional[str] = None
    source: Optional[str] = "mobile_app"


class TrackingSessionStopRequest(BaseModel):
    session_id: str


class TrackingSessionResponse(BaseModel):
    session_id: str
    tourist_id: str
    user_id: str
    status: str
    started_at: str
    ended_at: Optional[str] = None
    last_sequence_number: int = 0
    sample_count: int = 0


class LocationHistoryListResponse(BaseModel):
    tourist_id: str
    items: List[LocationSampleResponse]
    total: int
    limit: int
    skip: int
