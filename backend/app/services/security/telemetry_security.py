"""
TourSafe Telemetry Security & GPS Spoofing Detection Engine.
Validates:
1. Coordinate Boundaries (Latitude [-90, 90], Longitude [-180, 180])
2. Impossible Movement / Teleportation (Calculates Haversine distance and speed > 350 m/s / 1260 km/h)
3. Mock Location Indicator flags
4. Monotonic Sequence Validation and Replay Attack Prevention
5. Timestamp Freshness (prevents future timestamps or historic replays)
"""

import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException, status

# Session state store: session_id -> { "last_seq": int, "last_lat": float, "last_lon": float, "last_ts": float }
_TELEMETRY_SESSION_STATE: Dict[str, Dict[str, Any]] = {}

MAX_ALLOWABLE_SPEED_MPS = 350.0  # Speed of sound / commercial jet speed threshold in meters/sec


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two lat/lon coordinates."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def validate_gps_sample(
    latitude: float,
    longitude: float,
    timestamp: str | datetime,
    is_mock: bool = False,
    session_id: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate GPS coordinate sanity and spoofing heuristics.
    Returns: (is_valid, rejection_reason)
    """
    # 1. Bounds check
    if not (-90.0 <= latitude <= 90.0):
        return False, f"Invalid latitude {latitude}: must be within [-90.0, 90.0]"
    if not (-180.0 <= longitude <= 180.0):
        return False, f"Invalid longitude {longitude}: must be within [-180.0, 180.0]"

    # 2. Mock location indicator
    if is_mock:
        return False, "Mock GPS provider flag detected. Physical GPS required."

    # 3. Timestamp verification
    try:
        if isinstance(timestamp, str):
            ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        else:
            ts = timestamp
        now = datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # Allow max 5 minutes future drift and max 24 hours historical delay
        time_diff = (ts - now).total_seconds()
        if time_diff > 300:
            return False, f"GPS timestamp is in the future ({time_diff:.1f}s skew)"
        if time_diff < -86400:
            return False, "GPS timestamp is excessively stale (>24h old)"
    except Exception as e:
        return False, f"Invalid timestamp format: {e}"

    # 4. Kinematic sanity check if session is tracked
    if session_id and session_id in _TELEMETRY_SESSION_STATE:
        state = _TELEMETRY_SESSION_STATE[session_id]
        last_lat = state.get("last_lat")
        last_lon = state.get("last_lon")
        last_ts = state.get("last_ts", 0.0)
        curr_ts = ts.timestamp()

        if last_lat is not None and last_lon is not None and curr_ts > last_ts:
            dt = curr_ts - last_ts
            if dt > 0:
                dist = haversine_distance_meters(last_lat, last_lon, latitude, longitude)
                speed = dist / dt
                if speed > MAX_ALLOWABLE_SPEED_MPS:
                    return False, f"Impossible kinematic velocity ({speed:.1f} m/s exceeds physical limit)"

    return True, None


def validate_telemetry_sequence_and_replay(
    session_id: str,
    sequence_number: int,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timestamp: Optional[float] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate sequence number ordering and prevent replay packets.
    """
    if not session_id:
        return True, None

    state = _TELEMETRY_SESSION_STATE.setdefault(session_id, {
        "last_seq": -1,
        "last_lat": None,
        "last_lon": None,
        "last_ts": 0.0,
    })

    last_seq = state["last_seq"]
    if sequence_number <= last_seq:
        return False, f"Replay or out-of-order telemetry packet (sequence {sequence_number} <= last {last_seq})"

    # Update session state
    state["last_seq"] = sequence_number
    if latitude is not None:
        state["last_lat"] = latitude
    if longitude is not None:
        state["last_lon"] = longitude
    if timestamp is not None:
        state["last_ts"] = timestamp

    return True, None


def reset_telemetry_security_stores():
    """Reset state for tests."""
    _TELEMETRY_SESSION_STATE.clear()
