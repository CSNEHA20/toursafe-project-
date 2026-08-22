"""
TourSafe Data Minimization, Precision Reduction & Purpose Limitation Core.
Provides utility functions to:
- Reduce location precision (geohash / coordinate truncation) for analytics/heatmaps.
- Mask/pseudonymize sensitive PII for non-privileged viewers and exports.
- Enforce purpose limitation filters on data retrieval queries.
"""

import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple


def minimize_coordinates(
    latitude: float,
    longitude: float,
    precision_level: str = "AGGREGATE",
) -> Tuple[float, float]:
    """
    Minimizes geospatial precision according to context.
    - EMERGENCY / SOS: 6 decimal places (~0.11m exact)
    - OPERATIONAL: 4 decimal places (~11m)
    - AGGREGATE / ANALYTICS / HEATMAPS: 2 decimal places (~1.1km)
    - CITY_LEVEL: 1 decimal place (~11km)
    """
    if precision_level in ("EMERGENCY", "SOS", "EXACT"):
        return round(latitude, 6), round(longitude, 6)
    elif precision_level == "OPERATIONAL":
        return round(latitude, 4), round(longitude, 4)
    elif precision_level == "CITY_LEVEL":
        return round(latitude, 1), round(longitude, 1)
    else:  # Default AGGREGATE / ANALYTICS
        return round(latitude, 2), round(longitude, 2)


def pseudonymize_identifier(identifier: str, salt: str = "toursafe_salt_v1") -> str:
    """
    Generates a deterministic pseudonymous identifier for analytics/logging.
    """
    if not identifier:
        return ""
    combined = f"{salt}:{identifier}"
    digest = hashlib.sha256(combined.encode("utf-8")).hexdigest()
    return f"anon_{digest[:12]}"


def mask_pii_string(value: Optional[str], mask_char: str = "*") -> str:
    """
    Masks sensitive personal strings (names, emails, phone numbers).
    """
    if not value:
        return ""
    if "@" in value:  # Email
        parts = value.split("@")
        local = parts[0]
        domain = parts[1] if len(parts) > 1 else ""
        masked_local = local[0] + (mask_char * max(1, len(local) - 2)) + (local[-1] if len(local) > 1 else "")
        return f"{masked_local}@{domain}"
    elif re.match(r"^\+?[0-9\-\s]{7,15}$", value):  # Phone
        clean = re.sub(r"[^\d]", "", value)
        if len(clean) > 4:
            return f"{mask_char * (len(clean) - 4)}{clean[-4:]}"
        return mask_char * len(clean)
    else:  # General Name / Text
        if len(value) <= 2:
            return mask_char * len(value)
        return value[0] + (mask_char * (len(value) - 2)) + value[-1]


def sanitize_payload_for_audit(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Strips raw PII, sensitive biometric/IMU feeds, passwords, and tokens before audit storage.
    """
    if not payload:
        return {}
    
    sensitive_keys = {
        "password", "password_hash", "token", "access_token", "refresh_token",
        "secret", "api_key", "raw_imu", "accelerometer", "gyroscope",
        "passport_number", "national_id", "aadhaar", "document_image",
        "image_data", "biometric"
    }

    sanitized = {}
    for k, v in payload.items():
        if k.lower() in sensitive_keys:
            sanitized[k] = "[REDACTED_FOR_PRIVACY]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_payload_for_audit(v)
        elif isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
            sanitized[k] = [sanitize_payload_for_audit(item) for item in v]
        else:
            sanitized[k] = v
    return sanitized
