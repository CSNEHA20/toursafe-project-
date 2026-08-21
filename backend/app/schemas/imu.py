import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class IMUQualityStateEnum(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    DEGRADED = "degraded"
    POOR = "poor"
    UNAVAILABLE = "unavailable"


class AccelerometerChannels(BaseModel):
    x: float = Field(..., description="Acceleration on X-axis (in g)")
    y: float = Field(..., description="Acceleration on Y-axis (in g)")
    z: float = Field(..., description="Acceleration on Z-axis (in g)")

    @field_validator("x", "y", "z")
    @classmethod
    def validate_finite_floats(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Accelerometer values must be finite numbers")
        return round(v, 6)


class GyroscopeChannels(BaseModel):
    x: float = Field(..., description="Angular velocity around X-axis (in rad/s)")
    y: float = Field(..., description="Angular velocity around Y-axis (in rad/s)")
    z: float = Field(..., description="Angular velocity around Z-axis (in rad/s)")

    @field_validator("x", "y", "z")
    @classmethod
    def validate_finite_floats(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Gyroscope values must be finite numbers")
        return round(v, 6)


class DerivedKinematics(BaseModel):
    acceleration_magnitude: float = Field(..., description="Euclidean magnitude sqrt(ax^2+ay^2+az^2) in g")
    angular_velocity_magnitude: float = Field(..., description="Euclidean magnitude sqrt(gx^2+gy^2+gz^2) in rad/s")

    @field_validator("acceleration_magnitude", "angular_velocity_magnitude")
    @classmethod
    def validate_magnitude(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or v < 0:
            raise ValueError("Magnitudes must be non-negative finite numbers")
        return round(v, 6)


class IMUSampleQuality(BaseModel):
    sensor_timestamp_delta_ms: float = Field(0.0, description="Accelerometer vs Gyroscope timestamp offset in ms")
    is_synchronized: bool = Field(True, description="Whether pairing met synchronization tolerance")
    quality_state: IMUQualityStateEnum = Field(IMUQualityStateEnum.EXCELLENT)


class IMUSampleIn(BaseModel):
    """
    Canonical client-submitted Synchronized IMU Sample.
    Note: tourist_id is derived securely from JWT auth and never trusted from body.
    """
    session_id: str = Field(..., description="ID of the active IMU / tracking session")
    sequence_number: int = Field(..., description="Monotonically increasing sequence number >= 1")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of sample")
    monotonic_timestamp_ms: Optional[float] = Field(None, description="Client monotonic clock value in ms")
    device_id: Optional[str] = Field(None, description="App installation device identifier")
    accelerometer: AccelerometerChannels
    gyroscope: GyroscopeChannels
    derived: Optional[DerivedKinematics] = None
    quality: Optional[IMUSampleQuality] = None

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
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if (parsed - now).total_seconds() > 600:
                raise ValueError("Timestamp is too far in the future")
        except ValueError as e:
            if "too far in the future" in str(e):
                raise
            raise ValueError(f"Invalid ISO 8601 timestamp string: '{v}'")
        return v

    def calculate_server_magnitudes(self) -> DerivedKinematics:
        """Recompute magnitudes on server for validation."""
        ax, ay, az = self.accelerometer.x, self.accelerometer.y, self.accelerometer.z
        gx, gy, gz = self.gyroscope.x, self.gyroscope.y, self.gyroscope.z
        a_mag = math.sqrt(ax * ax + ay * ay + az * az)
        g_mag = math.sqrt(gx * gx + gy * gy + gz * gz)
        return DerivedKinematics(
            acceleration_magnitude=round(a_mag, 6),
            angular_velocity_magnitude=round(g_mag, 6),
        )


class IMUSampleBatchIn(BaseModel):
    """Batch of IMU samples for efficient high-frequency network transmission."""
    session_id: str
    samples: List[IMUSampleIn]


class IMUTelemetryAck(BaseModel):
    """Lightweight server acknowledgement for IMU sample ingestion."""
    status: str = "accepted"
    session_id: str
    sequence_number: int
    server_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    recomputed_acceleration_magnitude: float
    recomputed_angular_velocity_magnitude: float


class IMUBatchAck(BaseModel):
    """Lightweight batch ingestion acknowledgement."""
    status: str = "accepted"
    session_id: str
    accepted_count: int
    last_sequence_number: int
    server_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class IMUSessionStartRequest(BaseModel):
    device_id: Optional[str] = None
    source: Optional[str] = "mobile_app"


class IMUSessionResponse(BaseModel):
    session_id: str
    tourist_id: str
    user_id: str
    status: str
    started_at: str
    ended_at: Optional[str] = None
    last_sequence_number: int = 0
    sample_count: int = 0
