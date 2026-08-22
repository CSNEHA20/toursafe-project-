"""
TourSafe Safety Signal Pipeline & Normalization

Constructs canonical SafetySignal envelopes from disparate subsystem outputs:
- GPS / LocationService
- Geo-fencing / GeofenceEngine
- LSTM Motion Anomaly / RealtimeInferenceEngine
- Telemetry Quality / TelemetryIngestionService
- Tracking Sessions & Tourist Itinerary Context
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple

from ...schemas.safety import SafetySignal, SignalQuality, SignalType
from .config import safety_config

logger = logging.getLogger("toursafe.safety.signals")


def parse_timestamp_iso(ts_str: Optional[str]) -> datetime:
    """Parses an ISO timestamp safely into UTC datetime."""
    if not ts_str:
        return datetime.now(timezone.utc)
    try:
        clean = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)


def compute_signal_age_seconds(signal_timestamp: str, now: Optional[datetime] = None) -> float:
    """Calculates age in seconds from timestamp string."""
    now_dt = now or datetime.now(timezone.utc)
    sig_dt = parse_timestamp_iso(signal_timestamp)
    return max(0.0, (now_dt - sig_dt).total_seconds())


def is_signal_fresh(signal: SafetySignal, now: Optional[datetime] = None) -> bool:
    """
    Evaluates whether a transient safety signal is fresh based on subsystem-specific freshness windows.
    """
    age = compute_signal_age_seconds(signal.timestamp, now)

    if signal.signal_type in (SignalType.GPS_LOCATION_UPDATE, SignalType.GPS_UNCERTAIN):
        return age <= safety_config.gps_freshness_seconds
    elif signal.signal_type == SignalType.GPS_STALE:
        return age <= safety_config.signal_expiry_seconds
    elif signal.signal_type in (SignalType.ANOMALY_DETECTED, SignalType.ANOMALY_CLEARED):
        return age <= safety_config.anomaly_freshness_seconds
    elif signal.signal_type in (SignalType.TELEMETRY_GOOD, SignalType.TELEMETRY_DEGRADED, SignalType.TELEMETRY_OFFLINE):
        return age <= safety_config.telemetry_freshness_seconds
    elif signal.signal_type in (SignalType.ZONE_ENTERED, SignalType.ZONE_EXITED, SignalType.ZONE_DWELL):
        return age <= safety_config.zone_freshness_seconds
    elif signal.signal_type in (SignalType.TRACKING_ACTIVE, SignalType.TRACKING_STOPPED):
        return age <= safety_config.signal_expiry_seconds
    elif signal.signal_type == SignalType.ITINERARY_DEVIATION:
        return age <= safety_config.zone_freshness_seconds

    return age <= safety_config.signal_expiry_seconds


class SafetySignalFactory:
    """
    Normalizes domain payloads from other services into canonical SafetySignal objects.
    """

    @staticmethod
    def create_anomaly_signal(
        tourist_id: str,
        session_id: Optional[str],
        state: str,  # "normal", "warning", "anomalous"
        score: float,
        threshold: float,
        consecutive_windows: int = 1,
        quality: str = "good",
        model_version: str = "v1.0.0",
        timestamp: Optional[str] = None,
    ) -> SafetySignal:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        is_anom = state.lower() in ("anomalous", "warning") and score >= threshold

        sig_quality = SignalQuality.GOOD
        if quality.lower() in ("degraded", "moderate"):
            sig_quality = SignalQuality.DEGRADED
        elif quality.lower() in ("poor", "unreliable"):
            sig_quality = SignalQuality.POOR

        return SafetySignal(
            signal_type=SignalType.ANOMALY_DETECTED if is_anom else SignalType.ANOMALY_CLEARED,
            tourist_id=tourist_id,
            session_id=session_id,
            timestamp=ts,
            source="lstm_inference_engine",
            value={
                "state": state,
                "score": score,
                "threshold": threshold,
                "is_anomalous": is_anom,
                "consecutive_windows": consecutive_windows,
            },
            quality=sig_quality,
            metadata={
                "model_version": model_version,
                "threshold_ratio": round(score / max(threshold, 0.0001), 2),
            },
        )

    @staticmethod
    def create_gps_signal(
        tourist_id: str,
        session_id: Optional[str],
        latitude: float,
        longitude: float,
        accuracy: float,
        staleness_state: str = "live",
        speed: Optional[float] = None,
        timestamp: Optional[str] = None,
    ) -> SafetySignal:
        ts = timestamp or datetime.now(timezone.utc).isoformat()

        if accuracy <= safety_config.gps_accuracy_high_threshold_meters:
            quality = SignalQuality.EXCELLENT
        elif accuracy <= safety_config.gps_accuracy_poor_threshold_meters:
            quality = SignalQuality.GOOD
        else:
            quality = SignalQuality.POOR

        if staleness_state.lower() in ("stale", "unknown"):
            sig_type = SignalType.GPS_STALE
            quality = SignalQuality.STALE
        elif accuracy > safety_config.gps_accuracy_poor_threshold_meters:
            sig_type = SignalType.GPS_UNCERTAIN
            quality = SignalQuality.DEGRADED
        else:
            sig_type = SignalType.GPS_LOCATION_UPDATE

        return SafetySignal(
            signal_type=sig_type,
            tourist_id=tourist_id,
            session_id=session_id,
            timestamp=ts,
            source="gps_location_service",
            value={
                "latitude": latitude,
                "longitude": longitude,
                "accuracy": accuracy,
                "speed": speed,
                "staleness": staleness_state,
            },
            quality=quality,
            metadata={"accuracy_meters": accuracy, "staleness": staleness_state},
        )

    @staticmethod
    def create_geofence_signal(
        tourist_id: str,
        session_id: Optional[str],
        zone_id: str,
        zone_name: str,
        zone_type: str,
        risk_level: str,
        membership_state: str,  # "inside", "outside", "uncertain", "stale"
        dwell_duration_seconds: Optional[float] = None,
        confidence_score: float = 1.0,
        timestamp: Optional[str] = None,
    ) -> SafetySignal:
        ts = timestamp or datetime.now(timezone.utc).isoformat()

        if membership_state.lower() == "inside":
            sig_type = SignalType.ZONE_ENTERED
        elif membership_state.lower() == "outside":
            sig_type = SignalType.ZONE_EXITED
        elif membership_state.lower() == "uncertain":
            sig_type = SignalType.GPS_UNCERTAIN
        else:
            sig_type = SignalType.ZONE_ENTERED

        if dwell_duration_seconds and dwell_duration_seconds > 0:
            sig_type = SignalType.ZONE_DWELL

        quality = SignalQuality.GOOD if confidence_score >= 0.7 else SignalQuality.DEGRADED

        return SafetySignal(
            signal_type=sig_type,
            tourist_id=tourist_id,
            session_id=session_id,
            timestamp=ts,
            source="geofence_engine",
            value={
                "zone_id": zone_id,
                "zone_name": zone_name,
                "zone_type": zone_type,
                "risk_level": risk_level,
                "membership_state": membership_state,
                "dwell_duration_seconds": dwell_duration_seconds,
            },
            quality=quality,
            metadata={
                "confidence_score": confidence_score,
                "risk_rank": safety_config.zone_risk_levels.get(risk_level.lower(), 1),
            },
        )

    @staticmethod
    def create_telemetry_signal(
        tourist_id: str,
        session_id: Optional[str],
        overall_quality: str,  # "good", "degraded", "poor", "unavailable"
        observed_frequency_hz: float,
        completeness_ratio: float,
        network_status: str = "online",
        timestamp: Optional[str] = None,
    ) -> SafetySignal:
        ts = timestamp or datetime.now(timezone.utc).isoformat()

        if overall_quality.lower() == "good" and observed_frequency_hz >= safety_config.imu_min_acceptable_freq_hz:
            sig_type = SignalType.TELEMETRY_GOOD
            quality = SignalQuality.GOOD
        elif overall_quality.lower() in ("degraded", "moderate") or completeness_ratio < safety_config.telemetry_min_completeness_ratio:
            sig_type = SignalType.TELEMETRY_DEGRADED
            quality = SignalQuality.DEGRADED
        elif overall_quality.lower() in ("poor", "unreliable"):
            sig_type = SignalType.TELEMETRY_DEGRADED
            quality = SignalQuality.POOR
        else:
            sig_type = SignalType.TELEMETRY_OFFLINE
            quality = SignalQuality.UNKNOWN

        return SafetySignal(
            signal_type=sig_type,
            tourist_id=tourist_id,
            session_id=session_id,
            timestamp=ts,
            source="telemetry_pipeline",
            value={
                "overall_quality": overall_quality,
                "observed_frequency_hz": observed_frequency_hz,
                "completeness_ratio": completeness_ratio,
                "network_status": network_status,
            },
            quality=quality,
            metadata={
                "frequency_hz": observed_frequency_hz,
                "completeness": completeness_ratio,
            },
        )

    @staticmethod
    def create_tracking_signal(
        tourist_id: str,
        session_id: Optional[str],
        tracking_status: str,  # "active", "paused", "stopped", "stale"
        timestamp: Optional[str] = None,
    ) -> SafetySignal:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        is_active = tracking_status.lower() == "active"

        return SafetySignal(
            signal_type=SignalType.TRACKING_ACTIVE if is_active else SignalType.TRACKING_STOPPED,
            tourist_id=tourist_id,
            session_id=session_id,
            timestamp=ts,
            source="tracking_session_service",
            value={"tracking_status": tracking_status},
            quality=SignalQuality.GOOD if is_active else SignalQuality.UNKNOWN,
            metadata={"status": tracking_status},
        )

    @staticmethod
    def create_itinerary_deviation_signal(
        tourist_id: str,
        session_id: Optional[str],
        planned_destination: str,
        distance_meters: float,
        timestamp: Optional[str] = None,
    ) -> SafetySignal:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        return SafetySignal(
            signal_type=SignalType.ITINERARY_DEVIATION,
            tourist_id=tourist_id,
            session_id=session_id,
            timestamp=ts,
            source="itinerary_service",
            value={
                "planned_destination": planned_destination,
                "distance_meters": distance_meters,
            },
            quality=SignalQuality.GOOD,
            metadata={"distance_meters": distance_meters},
        )
