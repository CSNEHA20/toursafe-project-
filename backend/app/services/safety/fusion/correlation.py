"""
TourSafe Signal Correlation & False Positive Reduction Engine

Cross-correlates multi-dimensional signals to identify actionable compound patterns,
detect benign false alarm signatures, and calculate dynamic contextual dampening.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple

from ....schemas.safety import NormalizedSafetyFeatures, SignalCorrelationResult
from ..config import safety_config

logger = logging.getLogger("toursafe.safety.fusion.correlation")


class SignalCorrelationEngine:
    """
    Evaluates multi-signal interactions to reduce false alarms and amplify corroborated hazards.
    """

    @classmethod
    def evaluate_correlation(
        cls,
        features: NormalizedSafetyFeatures,
        raw_signals: Dict[str, Any],
        tourist_context: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> SignalCorrelationResult:
        ctx = tourist_context or {}
        notes: List[str] = []
        matched_signatures: List[str] = []

        dampening = 1.0
        fp_prob = 0.05
        is_suppressed = False
        primary_pattern = "UNIFORM_INDEPENDENT_SIGNALS"

        # Extract underlying context metrics
        gps_val = raw_signals.get("GPS_LOCATION_UPDATE") or raw_signals.get("GPS_UNCERTAIN") or {}
        speed_mps = float(gps_val.get("speed", 0.0) or 0.0) if isinstance(gps_val, dict) else 0.0
        speed_kmh = speed_mps * 3.6

        anomaly_val = raw_signals.get("ANOMALY_DETECTED") or {}
        consecutive_anom = int(anomaly_val.get("consecutive_windows", 1)) if isinstance(anomaly_val, dict) else 0

        # Check if tourist recently confirmed they are safe
        recent_safe_check = ctx.get("recent_safe_check_confirmed", False)
        safe_check_age_sec = float(ctx.get("safe_check_age_seconds", 9999.0))

        # -------------------------------------------------------------------
        # 1. Benign False Alarm Signature: Highway Transit Road Roughness
        # -------------------------------------------------------------------
        if (
            features.motion_anomaly_norm > 0.35
            and speed_kmh >= 45.0
            and features.geospatial_hazard_norm < 0.3
            and features.kinematic_shock_norm < 0.7
        ):
            primary_pattern = "BENIGN_HIGHWAY_TRANSIT_ROUGH_ROAD"
            matched_signatures.append("SIGNATURE_TRANSIT_VIBRATION")
            dampening = 0.30
            fp_prob = 0.85
            is_suppressed = True
            notes.append(f"High motion vibration during rapid vehicle transit ({speed_kmh:.1f} km/h); filtered as road surface roughness")

        # -------------------------------------------------------------------
        # 2. Benign False Alarm Signature: Transient Phone Drop
        # -------------------------------------------------------------------
        elif (
            features.kinematic_shock_norm > 0.4
            and consecutive_anom <= 1
            and features.geospatial_hazard_norm < 0.3
            and features.itinerary_deviation_norm < 0.2
        ):
            primary_pattern = "TRANSIENT_PHONE_DROP"
            matched_signatures.append("SIGNATURE_ISOLATED_IMPACT_SPIKE")
            dampening = 0.25
            fp_prob = 0.78
            is_suppressed = True
            notes.append("Isolated transient kinematic impact without persistent anomaly or hazard zone; likely dropped device")

        # -------------------------------------------------------------------
        # 3. Benign False Alarm Signature: Low Battery Power Saving Mode
        # -------------------------------------------------------------------
        elif (
            features.telemetry_degradation_norm > 0.4
            and ctx.get("battery_level", 1.0) < 0.15
            and features.motion_anomaly_norm < 0.2
            and features.geospatial_hazard_norm < 0.2
        ):
            primary_pattern = "DEVICE_BATTERY_SAVING_MODE"
            matched_signatures.append("SIGNATURE_POWER_SAVING_PACKET_LOSS")
            dampening = 0.40
            fp_prob = 0.70
            is_suppressed = True
            notes.append("Telemetry degradation attributed to critical device battery saving mode rather than emergency outage")

        # -------------------------------------------------------------------
        # 4. Benign False Alarm Signature: Day-Time Amenity / Rest Stop Detour
        # -------------------------------------------------------------------
        elif (
            features.itinerary_deviation_norm > 0.3
            and features.temporal_risk_norm < 0.25
            and features.geospatial_hazard_norm < 0.25
            and features.motion_anomaly_norm < 0.2
            and features.itinerary_deviation_norm < 0.6
        ):
            primary_pattern = "BENIGN_REST_STOP_DETOUR"
            matched_signatures.append("SIGNATURE_DAYTIME_AMENITY_STOP")
            dampening = 0.50
            fp_prob = 0.60
            notes.append("Minor daytime route deviation in safe zone; characteristic of tourist rest stop or scenic waypoint")

        # -------------------------------------------------------------------
        # 5. Corroborated High-Risk Signature: High-Speed Vehicular Collision
        # -------------------------------------------------------------------
        elif (
            features.kinematic_shock_norm > 0.65
            and (speed_kmh > 30.0 or features.motion_anomaly_norm > 0.7)
            and (features.geospatial_hazard_norm > 0.4 or features.itinerary_deviation_norm > 0.3)
        ):
            primary_pattern = "CORROBORATED_VEHICULAR_CRASH"
            matched_signatures.append("SIGNATURE_HIGH_G_DECELERATION_IMPACT")
            dampening = 1.0
            fp_prob = 0.02
            is_suppressed = False
            notes.append("Severe kinematic impact coupled with rapid motion disturbance outside planned corridor; high crash probability")

        # -------------------------------------------------------------------
        # 6. Corroborated High-Risk Signature: Trail Fall & Immobility in Hazard
        # -------------------------------------------------------------------
        elif (
            features.kinematic_shock_norm > 0.5
            and features.motion_anomaly_norm > 0.5
            and features.geospatial_hazard_norm >= 0.6
        ):
            primary_pattern = "CORROBORATED_HAZARD_FALL"
            matched_signatures.append("SIGNATURE_HAZARD_ZONE_IMPACT")
            dampening = 1.0
            fp_prob = 0.03
            is_suppressed = False
            notes.append("Impact shock and persistent motion disruption confirmed inside designated restricted/danger zone")

        # -------------------------------------------------------------------
        # 7. Corroborated High-Risk Signature: Night Off-Route Danger Containment
        # -------------------------------------------------------------------
        elif (
            features.temporal_risk_norm > 0.5
            and features.itinerary_deviation_norm > 0.4
            and (features.geospatial_hazard_norm > 0.5 or features.telemetry_degradation_norm > 0.5)
        ):
            primary_pattern = "NIGHT_OFF_ROUTE_ISOLATION"
            matched_signatures.append("SIGNATURE_NOCTURNAL_OFF_CORRIDOR")
            dampening = 1.0
            fp_prob = 0.05
            is_suppressed = False
            notes.append("Nocturnal isolation: Tourist off planned itinerary in high-risk/degraded coverage area during off-hours")

        # -------------------------------------------------------------------
        # 8. Tourist Active Safe Confirmation Dampening
        # -------------------------------------------------------------------
        if recent_safe_check and safe_check_age_sec < 600.0 and features.kinematic_shock_norm < 0.8:
            matched_signatures.append("SIGNATURE_USER_CONFIRMED_SAFE")
            dampening = min(dampening, 0.20)
            fp_prob = max(fp_prob, 0.90)
            is_suppressed = True
            notes.append(f"Tourist confirmed safety status via check-in {int(safe_check_age_sec)}s ago; active dampening applied")

        return SignalCorrelationResult(
            correlated_pattern=primary_pattern,
            dampening_factor=round(dampening, 4),
            false_positive_probability=round(fp_prob, 4),
            is_false_alarm_suppressed=is_suppressed,
            matched_signatures=matched_signatures,
            correlation_notes=notes,
        )
