import math
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class TelemetryPacketType(str, Enum):
    GPS_SAMPLE = "gps.sample"
    IMU_SAMPLE = "imu.sample"
    TELEMETRY_SAMPLE = "telemetry.sample"
    TELEMETRY_WINDOW = "telemetry.window"


class QualityStateEnum(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    DEGRADED = "degraded"
    POOR = "poor"
    UNAVAILABLE = "unavailable"


class SessionStatusEnum(str, Enum):
    STARTING = "starting"
    ACTIVE = "active"
    PAUSED = "paused"
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"
    ERROR = "error"


# ─── Sensor Component Schemas ─────────────────────────────────────────────────

class GPSPayload(BaseModel):
    latitude: float = Field(..., description="WGS84 latitude between -90 and 90")
    longitude: float = Field(..., description="WGS84 longitude between -180 and 180")
    altitude: Optional[float] = Field(None, description="Altitude in meters above WGS84 ellipsoid")
    accuracy: Optional[float] = Field(None, description="Horizontal accuracy radius in meters")
    speed: Optional[float] = Field(None, description="Instantaneous velocity over ground in m/s")
    heading: Optional[float] = Field(None, description="Direction of travel in degrees (0-360)")
    provider: Optional[str] = Field("gps", description="Location provider: gps, fused, network")

    @field_validator("latitude")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or not (-90.0 <= v <= 90.0):
            raise ValueError("Latitude must be a valid float between -90.0 and 90.0")
        return round(v, 7)

    @field_validator("longitude")
    @classmethod
    def validate_lon(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or not (-180.0 <= v <= 180.0):
            raise ValueError("Longitude must be a valid float between -180.0 and 180.0")
        return round(v, 7)

    @field_validator("accuracy", "speed", "heading")
    @classmethod
    def validate_non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if math.isnan(v) or math.isinf(v) or v < 0:
                raise ValueError("Value must be a non-negative finite number")
            return round(v, 2)
        return v


class AccelerometerChannels(BaseModel):
    x: float = Field(..., description="Acceleration along X-axis in g (9.81 m/s^2)")
    y: float = Field(..., description="Acceleration along Y-axis in g")
    z: float = Field(..., description="Acceleration along Z-axis in g")

    @field_validator("x", "y", "z")
    @classmethod
    def validate_finite(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Accelerometer channel values must be finite numbers")
        return round(v, 6)


class GyroscopeChannels(BaseModel):
    x: float = Field(..., description="Angular velocity around X-axis in rad/s")
    y: float = Field(..., description="Angular velocity around Y-axis in rad/s")
    z: float = Field(..., description="Angular velocity around Z-axis in rad/s")

    @field_validator("x", "y", "z")
    @classmethod
    def validate_finite(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Gyroscope channel values must be finite numbers")
        return round(v, 6)


class DerivedKinematics(BaseModel):
    acceleration_magnitude: float = Field(..., description="Magnitude of acceleration vector sqrt(ax^2+ay^2+az^2) in g")
    angular_velocity_magnitude: float = Field(..., description="Magnitude of angular velocity sqrt(gx^2+gy^2+gz^2) in rad/s")

    @field_validator("acceleration_magnitude", "angular_velocity_magnitude")
    @classmethod
    def validate_magnitude(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or v < 0:
            raise ValueError("Kinematic magnitude must be a non-negative finite float")
        return round(v, 6)


class QualityMetrics(BaseModel):
    gps_quality: QualityStateEnum = Field(QualityStateEnum.UNAVAILABLE)
    imu_quality: QualityStateEnum = Field(QualityStateEnum.EXCELLENT)
    synchronization_quality: QualityStateEnum = Field(QualityStateEnum.EXCELLENT)
    network_quality: QualityStateEnum = Field(QualityStateEnum.GOOD)
    overall_quality: QualityStateEnum = Field(QualityStateEnum.GOOD)
    sensor_timestamp_delta_ms: float = Field(0.0, description="Accelerometer to Gyroscope offset in ms")
    observed_frequency_hz: Optional[float] = Field(None, description="Empirical sampling frequency")
    transport_latency_ms: Optional[float] = Field(None, description="Transport delay estimate in ms")


# ─── Canonical Telemetry Sample ───────────────────────────────────────────────

class TelemetrySample(BaseModel):
    """
    Canonical Telemetry Sample model.
    Flexible enough for GPS-only, IMU-only, or synchronized composite telemetry packets.
    """
    packet_id: str = Field(default_factory=lambda: f"pkt_{uuid.uuid4().hex[:12]}")
    packet_type: TelemetryPacketType = Field(default=TelemetryPacketType.TELEMETRY_SAMPLE)
    session_id: str = Field(..., description="Active telemetry tracking session ID")
    tourist_id: str = Field(..., description="Authenticated tourist ID")
    device_id: Optional[str] = Field(None, description="Hardware / Installation identifier")
    sequence_number: int = Field(..., description="Monotonically increasing sequence number per session")
    timestamp: str = Field(..., description="Original sensor acquisition timestamp (ISO 8601 UTC)")
    received_at: Optional[str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Payload components (all optional to allow single-modality streams)
    gps: Optional[GPSPayload] = None
    accelerometer: Optional[AccelerometerChannels] = None
    gyroscope: Optional[GyroscopeChannels] = None
    derived: Optional[DerivedKinematics] = None
    quality: Optional[QualityMetrics] = None

    # Contextual metadata
    is_background: bool = Field(False, description="Whether sample was recorded while app was in background")
    network_status: Optional[str] = Field("online", description="Client network state: online, offline, replaying")

    @field_validator("sequence_number")
    @classmethod
    def validate_seq(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Sequence number must be a positive integer (>= 1)")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_sensor_timestamp(cls, v: str) -> str:
        try:
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            diff_sec = (parsed - now).total_seconds()
            if diff_sec > 600:  # > 10 minutes in future
                raise ValueError("Timestamp cannot be more than 10 minutes in the future")
            if diff_sec < -86400:  # > 24 hours old
                raise ValueError("Timestamp cannot be older than 24 hours for live ingestion")
        except ValueError as e:
            if "Timestamp cannot" in str(e):
                raise
            raise ValueError(f"Invalid ISO 8601 timestamp string: '{v}'")
        return v

    def calculate_server_magnitudes(self) -> Optional[DerivedKinematics]:
        """Compute server-side kinematic magnitudes if IMU data is present."""
        if self.accelerometer and self.gyroscope:
            ax, ay, az = self.accelerometer.x, self.accelerometer.y, self.accelerometer.z
            gx, gy, gz = self.gyroscope.x, self.gyroscope.y, self.gyroscope.z
            a_mag = math.sqrt(ax * ax + ay * ay + az * az)
            g_mag = math.sqrt(gx * gx + gy * gy + gz * gz)
            return DerivedKinematics(
                acceleration_magnitude=round(a_mag, 6),
                angular_velocity_magnitude=round(g_mag, 6),
            )
        elif self.accelerometer:
            ax, ay, az = self.accelerometer.x, self.accelerometer.y, self.accelerometer.z
            a_mag = math.sqrt(ax * ax + ay * ay + az * az)
            return DerivedKinematics(
                acceleration_magnitude=round(a_mag, 6),
                angular_velocity_magnitude=0.0,
            )
        return None


# ─── Canonical Telemetry Packet Envelope ──────────────────────────────────────

class TelemetryPacketEnvelope(BaseModel):
    """
    Standard Telemetry Envelope.
    Guarantees structural consistency across HTTP and WebSocket transports.
    """
    packet_id: str = Field(default_factory=lambda: f"pkt_{uuid.uuid4().hex[:12]}")
    packet_type: TelemetryPacketType
    session_id: str
    tourist_id: Optional[str] = None  # Injected/verified from authentication
    device_id: Optional[str] = None
    sequence_number: int
    timestamp: str
    protocol_version: int = Field(default=1, description="TourSafe Telemetry Protocol Version")
    payload: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("sequence_number")
    @classmethod
    def validate_seq_envelope(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Sequence number must be >= 1")
        return v

    @field_validator("protocol_version")
    @classmethod
    def validate_proto(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Protocol version must be >= 1")
        return v


class TelemetryBatchRequest(BaseModel):
    """Bounded batch of telemetry packets for high-efficiency ingestion / offline replay."""
    session_id: str
    packets: List[TelemetryPacketEnvelope] = Field(..., max_length=500)


# ─── Telemetry Acknowledgement Schemas ────────────────────────────────────────

class TelemetryAckStatus(str, Enum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    OUT_OF_ORDER = "out_of_order"
    REJECTED = "rejected"
    INVALID = "invalid"


class TelemetryAck(BaseModel):
    status: TelemetryAckStatus
    packet_id: str
    session_id: str
    sequence_number: int
    highest_contiguous_sequence: int
    server_received_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    detail: Optional[str] = None


class TelemetryBatchAck(BaseModel):
    status: str = "batch_processed"
    session_id: str
    accepted_count: int
    duplicate_count: int
    out_of_order_count: int
    rejected_count: int
    highest_contiguous_sequence: int
    server_received_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ─── Temporal Window Schema (Foundation for AI / ML) ─────────────────────────

class TelemetryWindow(BaseModel):
    """
    Canonical 3-second Temporal Telemetry Window.
    Operates on synchronized IMU samples aligned with temporal GPS context.
    Standard input contract for future AI inference engines.
    """
    window_id: str = Field(default_factory=lambda: f"win_{uuid.uuid4().hex[:12]}")
    session_id: str
    tourist_id: str
    device_id: Optional[str] = None
    window_start: str = Field(..., description="ISO 8601 start timestamp")
    window_end: str = Field(..., description="ISO 8601 end timestamp")
    duration_seconds: float = Field(3.0, description="Nominal window duration in seconds")
    stride_seconds: float = Field(1.0, description="Configured stride in seconds")
    sample_count: int
    observed_frequency_hz: float
    completeness_ratio: float = Field(..., description="Observed vs expected sample count ratio (0.0 to 1.0+)")
    is_valid: bool = Field(True, description="Whether window satisfies validity criteria")
    validation_errors: List[str] = Field(default_factory=list)
    quality: QualityMetrics
    samples: List[TelemetrySample]
    gps_context: Optional[GPSPayload] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ─── Telemetry Session Schemas ───────────────────────────────────────────────

class TelemetrySessionStartRequest(BaseModel):
    device_id: Optional[str] = None
    source: Optional[str] = "mobile_app"
    sampling_rate_target_hz: float = Field(default=50.0, ge=1.0, le=100.0)


class TelemetrySessionStopRequest(BaseModel):
    session_id: str


class TelemetrySessionMetrics(BaseModel):
    total_packets: int = 0
    accepted_packets: int = 0
    duplicate_packets: int = 0
    invalid_packets: int = 0
    out_of_order_packets: int = 0
    estimated_missing_packets: int = 0
    reconnection_count: int = 0
    last_gap_duration_ms: float = 0.0
    last_sequence_number: int = 0
    highest_contiguous_sequence: int = 0
    last_packet_timestamp: Optional[str] = None
    last_gps_timestamp: Optional[str] = None
    last_imu_timestamp: Optional[str] = None
    window_count: int = 0
    valid_window_count: int = 0
    invalid_window_count: int = 0


class TelemetrySessionResponse(BaseModel):
    session_id: str
    tourist_id: str
    user_id: str
    device_id: Optional[str] = None
    status: SessionStatusEnum
    started_at: str
    ended_at: Optional[str] = None
    metrics: TelemetrySessionMetrics = Field(default_factory=TelemetrySessionMetrics)


# ─── Operational Status & Diagnostics Schemas ─────────────────────────────────

class TouristTelemetryStatusResponse(BaseModel):
    tourist_id: str
    active_session_id: Optional[str] = None
    tracking_status: SessionStatusEnum
    imu_active: bool
    gps_active: bool
    last_telemetry_timestamp: Optional[str] = None
    observed_imu_frequency_hz: Optional[float] = None
    observed_gps_frequency_hz: Optional[float] = None
    connection_state: str
    quality: QualityMetrics
    metrics: TelemetrySessionMetrics
    recent_windows_generated: int = 0


class AuthorityTelemetryStatusResponse(BaseModel):
    """
    Summarized operational status for Authority monitoring.
    Contains NO raw 50 Hz IMU data stream.
    """
    tourist_id: str
    session_id: Optional[str] = None
    tracking_status: SessionStatusEnum
    last_location_timestamp: Optional[str] = None
    last_telemetry_timestamp: Optional[str] = None
    gps_quality: QualityStateEnum
    imu_quality: QualityStateEnum
    overall_quality: QualityStateEnum
    connection_state: str
    is_stale: bool
    age_seconds: Optional[float] = None


class TelemetryDiagnosticsResponse(BaseModel):
    queue_depth: int
    queue_capacity: int
    enqueue_failures: int
    processing_latency_ms: float
    total_ingested_today: int
    active_sessions_count: int
    redis_health: Dict[str, Any]
    mongodb_persistence_ok: bool
