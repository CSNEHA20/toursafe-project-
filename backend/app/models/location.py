from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class GeoJSONPoint(BaseModel):
    """GeoJSON Point representation: coordinates are [longitude, latitude]"""
    type: str = "Point"
    coordinates: List[float]  # [longitude, latitude]


class LocationHistoryRecord(BaseModel):
    """
    Persistent Location Sample Document in MongoDB 'location_history'.
    """
    id: str = Field(default_factory=lambda: f"loc_{uuid.uuid4().hex[:12]}")
    location_id: str = Field(default_factory=lambda: f"loc_{uuid.uuid4().hex[:12]}")
    tourist_id: str
    user_id: str
    session_id: str
    device_id: Optional[str] = None
    timestamp: str  # ISO8601 UTC string
    latitude: float
    longitude: float
    location: GeoJSONPoint  # GeoJSON Point for MongoDB 2dsphere indexing
    altitude: Optional[float] = None
    accuracy: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    provider: Optional[str] = "gps"
    is_background: bool = False
    sequence_number: int = 1
    network_status: Optional[str] = "online"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TrackingSessionRecord(BaseModel):
    """
    Tracking Session Document in MongoDB 'tracking_sessions'.
    """
    id: str = Field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:12]}")
    session_id: str
    tourist_id: str
    user_id: str
    device_id: Optional[str] = None
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ended_at: Optional[str] = None
    status: str = "active"  # starting, active, paused, reconnecting, stopped, error
    last_sequence_number: int = 0
    last_location_timestamp: Optional[str] = None
    source: str = "mobile_app"
    sample_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
