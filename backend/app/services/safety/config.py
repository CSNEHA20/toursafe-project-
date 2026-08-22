"""
TourSafe Safety Rules Configuration - Version 1.0 (safety-rules-v1)

Deterministic, auditable parameter configurations for multi-signal safety reasoning,
risk fusion, and state transitions.
"""

from typing import Any, Dict
from pydantic import BaseModel, Field


class SafetyRulesConfig(BaseModel):
    # Rule engine version metadata
    rule_version: str = "safety-rules-v1"
    description: str = "TourSafe Multi-Signal Risk Fusion & Incident State Engine"

    # Signal freshness limits (seconds)
    gps_freshness_seconds: float = 30.0
    anomaly_freshness_seconds: float = 20.0
    telemetry_freshness_seconds: float = 15.0
    zone_freshness_seconds: float = 60.0
    signal_expiry_seconds: float = 120.0

    # Persistence parameters
    anomaly_min_persistence_windows: int = 2
    anomaly_high_persistence_windows: int = 4
    anomaly_high_score_multiplier: float = 1.5  # Score >= 1.5x threshold is high severity

    # Recovery parameters
    recovery_cooldown_seconds: float = 20.0  # Time required in RECOVERING before transitioning to NORMAL

    # Quality & Confidence thresholds
    gps_accuracy_high_threshold_meters: float = 25.0
    gps_accuracy_poor_threshold_meters: float = 50.0
    imu_min_acceptable_freq_hz: float = 35.0
    telemetry_min_completeness_ratio: float = 0.70

    # Risk Fusion Thresholds (0 - 100 composite score)
    risk_threshold_watch: float = 30.0
    risk_threshold_elevated: float = 60.0
    risk_threshold_candidate: float = 80.0
    risk_threshold_incident: float = 90.0

    # Risk Fusion Domain Weights
    weight_motion: float = 0.30
    weight_spatial: float = 0.28
    weight_itinerary: float = 0.16
    weight_environmental: float = 0.14
    weight_vulnerability: float = 0.12

    # Zone risk hierarchy
    zone_risk_levels: Dict[str, int] = Field(
        default_factory=lambda: {
            "safe": 1,
            "caution": 2,
            "restricted": 3,
            "danger": 4,
            "critical": 4,
        }
    )

    # Redis TTL
    redis_state_ttl_seconds: int = 300  # 5 minutes TTL for active safety state in Redis


safety_config = SafetyRulesConfig()
