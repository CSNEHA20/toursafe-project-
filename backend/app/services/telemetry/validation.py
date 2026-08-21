import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from ...schemas.telemetry import (
    AccelerometerChannels,
    DerivedKinematics,
    GPSPayload,
    GyroscopeChannels,
    TelemetryPacketEnvelope,
    TelemetryPacketType,
    TelemetrySample,
)

logger = logging.getLogger("toursafe.telemetry.validation")


class TelemetryValidationException(Exception):
    def __init__(self, message: str, error_type: str = "validation_error"):
        super().__init__(message)
        self.message = message
        self.error_type = error_type


class TelemetryValidator:
    """
    Validates packet envelopes, timestamps, kinematics, and normalizes into canonical TelemetrySample.
    """

    @staticmethod
    def validate_timestamp(timestamp_str: str) -> Tuple[datetime, float]:
        """
        Validates ISO 8601 timestamp string against current server UTC time.
        Returns parsed datetime and transport clock difference in milliseconds.
        """
        try:
            parsed = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except Exception as e:
            raise TelemetryValidationException(f"Invalid ISO 8601 timestamp format: {e}", "timestamp_format")

        now = datetime.now(timezone.utc)
        diff_sec = (now - parsed).total_seconds()

        # Reject timestamps too far in future (> 10 minutes)
        if diff_sec < -600.0:
            raise TelemetryValidationException("Timestamp is more than 10 minutes in the future", "future_timestamp")

        # Reject timestamps older than 24 hours
        if diff_sec > 86400.0:
            raise TelemetryValidationException("Timestamp is older than 24 hours", "expired_timestamp")

        transport_latency_ms = max(0.0, diff_sec * 1000.0)
        return parsed, transport_latency_ms

    @classmethod
    def normalize_envelope(
        cls,
        envelope: TelemetryPacketEnvelope,
        authenticated_tourist_id: str,
        user_id: str,
    ) -> TelemetrySample:
        """
        Transforms and validates a TelemetryPacketEnvelope into a clean TelemetrySample.
        Enforces that tourist_id comes from authenticated claims, not client spoofing.
        """
        # Validate timestamp
        _, transport_latency_ms = cls.validate_timestamp(envelope.timestamp)
        payload = envelope.payload or {}

        gps_payload: Optional[GPSPayload] = None
        accel_payload: Optional[AccelerometerChannels] = None
        gyro_payload: Optional[GyroscopeChannels] = None
        derived_payload: Optional[DerivedKinematics] = None

        packet_type = envelope.packet_type

        # 1. Parse GPS if present in payload or packet type is gps.sample
        if packet_type == TelemetryPacketType.GPS_SAMPLE or "gps" in payload or "latitude" in payload:
            raw_gps = payload.get("gps") or payload
            try:
                gps_payload = GPSPayload(
                    latitude=raw_gps["latitude"],
                    longitude=raw_gps["longitude"],
                    altitude=raw_gps.get("altitude"),
                    accuracy=raw_gps.get("accuracy"),
                    speed=raw_gps.get("speed"),
                    heading=raw_gps.get("heading"),
                    provider=raw_gps.get("provider", "gps"),
                )
            except KeyError as ke:
                raise TelemetryValidationException(f"GPS payload missing required field: {ke}", "missing_field")
            except Exception as e:
                raise TelemetryValidationException(f"GPS validation failed: {e}", "gps_invalid")

        # 2. Parse IMU (accelerometer & gyroscope) if present
        if packet_type == TelemetryPacketType.IMU_SAMPLE or "accelerometer" in payload or "ax" in payload:
            raw_accel = payload.get("accelerometer")
            if raw_accel:
                accel_payload = AccelerometerChannels(
                    x=raw_accel["x"],
                    y=raw_accel["y"],
                    z=raw_accel["z"],
                )
            elif "ax" in payload:
                accel_payload = AccelerometerChannels(
                    x=payload["ax"],
                    y=payload["ay"],
                    z=payload["az"],
                )

            raw_gyro = payload.get("gyroscope")
            if raw_gyro:
                gyro_payload = GyroscopeChannels(
                    x=raw_gyro["x"],
                    y=raw_gyro["y"],
                    z=raw_gyro["z"],
                )
            elif "gx" in payload:
                gyro_payload = GyroscopeChannels(
                    x=payload["gx"],
                    y=payload["gy"],
                    z=payload["gz"],
                )

        # 3. Calculate server-derived kinematics if IMU is present
        if accel_payload:
            ax, ay, az = accel_payload.x, accel_payload.y, accel_payload.z
            gx = gyro_payload.x if gyro_payload else 0.0
            gy = gyro_payload.y if gyro_payload else 0.0
            gz = gyro_payload.z if gyro_payload else 0.0

            a_mag = math.sqrt(ax * ax + ay * ay + az * az)
            g_mag = math.sqrt(gx * gx + gy * gy + gz * gz)
            derived_payload = DerivedKinematics(
                acceleration_magnitude=round(a_mag, 6),
                angular_velocity_magnitude=round(g_mag, 6),
            )

        # 4. Contextual metadata
        is_bg = bool(payload.get("is_background", False))
        net_status = payload.get("network_status", "online")

        return TelemetrySample(
            packet_id=envelope.packet_id,
            packet_type=packet_type,
            session_id=envelope.session_id,
            tourist_id=authenticated_tourist_id,
            device_id=envelope.device_id,
            sequence_number=envelope.sequence_number,
            timestamp=envelope.timestamp,
            gps=gps_payload,
            accelerometer=accel_payload,
            gyroscope=gyro_payload,
            derived=derived_payload,
            is_background=is_bg,
            network_status=net_status,
        )


telemetry_validator = TelemetryValidator()
