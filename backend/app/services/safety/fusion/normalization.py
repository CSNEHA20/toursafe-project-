"""
TourSafe Multi-Signal Normalization Engine

Standardizes heterogeneous raw safety signals across 8 dimensions into normalized [0.0 - 1.0] features:
1. motion_anomaly_norm: Normalized LSTM Autoencoder & IMU motion anomaly score
2. geospatial_hazard_norm: Normalized geofence containment, risk rank, dwell time, and boundary proximity
3. itinerary_deviation_norm: Normalized route corridor distance and schedule divergence
4. telemetry_degradation_norm: Normalized sensor degradation, jitter, packet loss, and battery drain
5. temporal_risk_norm: Normalized time-of-day (nighttime / off-hours / curfew) risk factor
6. trip_vulnerability_norm: Normalized traveler profile risk (solo, medical vulnerability, remote tour)
7. historical_risk_norm: Normalized historical incident frequency and regional risk heatmap
8. kinematic_shock_norm: Normalized high-G impact / fall / sudden deceleration vector
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional

from ....schemas.safety import NormalizedSafetyFeatures, SafetySignal, SignalType
from ..config import safety_config
from ..signals import compute_signal_age_seconds, is_signal_fresh, parse_timestamp_iso


class SignalNormalizer:
    """
    Normalizes multi-domain safety signals into standardized feature vectors.
    """

    @classmethod
    def normalize_signals(
        cls,
        active_signals: List[SafetySignal],
        tourist_context: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> NormalizedSafetyFeatures:
        curr_time = now or datetime.now(timezone.utc)
        fresh_signals = [s for s in active_signals if is_signal_fresh(s, curr_time)]

        # Extract domain signals
        anomaly_sig: Optional[SafetySignal] = None
        gps_sig: Optional[SafetySignal] = None
        zone_sigs: List[SafetySignal] = []
        telemetry_sig: Optional[SafetySignal] = None
        itinerary_sig: Optional[SafetySignal] = None
        temporal_sig: Optional[SafetySignal] = None
        trip_sig: Optional[SafetySignal] = None
        history_sig: Optional[SafetySignal] = None

        for s in fresh_signals:
            st = s.signal_type
            if st in (SignalType.ANOMALY_DETECTED, SignalType.ANOMALY_CLEARED):
                anomaly_sig = s
            elif st in (SignalType.GPS_LOCATION_UPDATE, SignalType.GPS_STALE, SignalType.GPS_UNCERTAIN):
                gps_sig = s
            elif st in (SignalType.ZONE_ENTERED, SignalType.ZONE_EXITED, SignalType.ZONE_DWELL):
                zone_sigs.append(s)
            elif st in (SignalType.TELEMETRY_GOOD, SignalType.TELEMETRY_DEGRADED, SignalType.TELEMETRY_OFFLINE):
                telemetry_sig = s
            elif st == SignalType.ITINERARY_DEVIATION:
                itinerary_sig = s
            elif st == SignalType.TEMPORAL_CONTEXT:
                temporal_sig = s
            elif st == SignalType.TRIP_CONTEXT:
                trip_sig = s
            elif st == SignalType.HISTORICAL_CONTEXT:
                history_sig = s

        # Context overrides
        ctx = tourist_context or {}

        # 1. Motion Anomaly Normalization
        motion_norm = cls._normalize_motion_anomaly(anomaly_sig)

        # 2. Kinematic Shock Normalization (Sudden impact / extreme jerk / rapid deceleration)
        shock_norm = cls._normalize_kinematic_shock(anomaly_sig, gps_sig)

        # 3. Geospatial Hazard Normalization
        geospatial_norm = cls._normalize_geospatial(zone_sigs, gps_sig)

        # 4. Itinerary Deviation Normalization
        itinerary_norm = cls._normalize_itinerary(itinerary_sig, gps_sig)

        # 5. Telemetry Degradation Normalization
        telemetry_norm = cls._normalize_telemetry(telemetry_sig, gps_sig)

        # 6. Temporal Risk Normalization
        temporal_norm = cls._normalize_temporal(temporal_sig, curr_time)

        # 7. Trip Vulnerability Normalization
        vulnerability_norm = cls._normalize_trip_vulnerability(trip_sig, ctx)

        # 8. Historical Risk Normalization
        history_norm = cls._normalize_historical(history_sig, ctx)

        return NormalizedSafetyFeatures(
            motion_anomaly_norm=round(min(1.0, max(0.0, motion_norm)), 4),
            geospatial_hazard_norm=round(min(1.0, max(0.0, geospatial_norm)), 4),
            itinerary_deviation_norm=round(min(1.0, max(0.0, itinerary_norm)), 4),
            telemetry_degradation_norm=round(min(1.0, max(0.0, telemetry_norm)), 4),
            temporal_risk_norm=round(min(1.0, max(0.0, temporal_norm)), 4),
            trip_vulnerability_norm=round(min(1.0, max(0.0, vulnerability_norm)), 4),
            historical_risk_norm=round(min(1.0, max(0.0, history_norm)), 4),
            kinematic_shock_norm=round(min(1.0, max(0.0, shock_norm)), 4),
        )

    @classmethod
    def _normalize_motion_anomaly(cls, anomaly_sig: Optional[SafetySignal]) -> float:
        if not anomaly_sig or anomaly_sig.signal_type == SignalType.ANOMALY_CLEARED:
            return 0.0

        val = anomaly_sig.value if isinstance(anomaly_sig.value, dict) else {}
        is_anom = val.get("is_anomalous", False)
        if not is_anom:
            return 0.0

        score = float(val.get("score", 0.0))
        threshold = max(float(val.get("threshold", 0.5)), 0.001)
        consecutive = int(val.get("consecutive_windows", 1))

        ratio = score / threshold
        # Base normalized score from reconstruction error ratio (ratio 1.0 -> 0.4, ratio 2.5 -> 0.8, ratio >= 4.0 -> 1.0)
        base = min(1.0, (ratio / 3.0) * 0.7)

        # Persistence compounding bonus
        persistence_bonus = min(0.3, (consecutive - 1) * 0.075)
        return min(1.0, base + persistence_bonus)

    @classmethod
    def _normalize_kinematic_shock(
        cls,
        anomaly_sig: Optional[SafetySignal],
        gps_sig: Optional[SafetySignal],
    ) -> float:
        shock_score = 0.0

        if anomaly_sig and isinstance(anomaly_sig.value, dict):
            val = anomaly_sig.value
            peak_g = float(val.get("peak_g", val.get("max_accel_norm", 0.0)))
            jerk = float(val.get("jerk_magnitude", 0.0))
            is_impact = val.get("motion_pattern") in ("impact", "fall", "struggle", "crash")

            if peak_g > 3.0:  # > 3G shock
                shock_score += min(0.7, (peak_g - 3.0) / 7.0)
            if jerk > 15.0:
                shock_score += min(0.3, jerk / 50.0)
            if is_impact:
                shock_score = max(shock_score, 0.65)

        # Check for rapid deceleration if GPS velocity available
        if gps_sig and isinstance(gps_sig.value, dict):
            speed_delta = float(gps_sig.value.get("speed_delta", 0.0))
            if speed_delta < -15.0:  # Rapid deceleration > 15 m/s (~54 km/h drop in one interval)
                shock_score = max(shock_score, 0.8)

        return min(1.0, shock_score)

    @classmethod
    def _normalize_geospatial(
        cls,
        zone_sigs: List[SafetySignal],
        gps_sig: Optional[SafetySignal],
    ) -> float:
        if not zone_sigs:
            return 0.0

        max_zone_score = 0.0

        for z in zone_sigs:
            if not isinstance(z.value, dict):
                continue
            membership = z.value.get("membership_state", "outside").lower()
            if membership not in ("inside", "uncertain", "approaching"):
                continue

            risk_level = z.value.get("risk_level", "safe").lower()
            rank = safety_config.zone_risk_levels.get(risk_level, 1)

            # Base score by risk rank (safe=0.0, caution=0.25, restricted=0.6, danger=0.9, critical=1.0)
            rank_map = {1: 0.0, 2: 0.25, 3: 0.60, 4: 0.90, 5: 1.0}
            base_score = rank_map.get(rank, 0.0)

            # Dwell duration amplification for high-risk zones
            dwell_sec = float(z.value.get("dwell_duration_seconds", 0.0) or 0.0)
            if rank >= 3 and dwell_sec > 0:
                dwell_bonus = min(0.2, (dwell_sec / 600.0) * 0.2)  # Max +0.2 over 10 min dwell
                base_score = min(1.0, base_score + dwell_bonus)

            # Hazard approach vector bonus if outside but approaching rapidly
            if membership == "approaching":
                approach_speed = float(z.value.get("approach_speed_mps", 0.0) or 0.0)
                distance_m = float(z.value.get("distance_to_boundary_meters", 100.0) or 100.0)
                if distance_m < 50.0 and approach_speed > 3.0:
                    base_score = max(base_score, 0.45 if rank >= 3 else 0.2)

            max_zone_score = max(max_zone_score, base_score)

        return max_zone_score

    @classmethod
    def _normalize_itinerary(
        cls,
        itinerary_sig: Optional[SafetySignal],
        gps_sig: Optional[SafetySignal],
    ) -> float:
        if not itinerary_sig or not isinstance(itinerary_sig.value, dict):
            return 0.0

        val = itinerary_sig.value
        dist_m = float(val.get("distance_meters", itinerary_sig.metadata.get("distance_meters", 0.0)))
        delay_min = float(val.get("delay_minutes", 0.0))
        is_missed_waypoint = bool(val.get("is_missed_waypoint", False))

        # Distance off-corridor score: 0m -> 0.0, 200m -> 0.2, 500m -> 0.5, 2000m+ -> 1.0
        dist_score = min(1.0, dist_m / 2000.0) if dist_m > 50.0 else 0.0

        # Schedule delay score: 0-15 min -> 0.0, 60 min -> 0.3, 180 min -> 0.7
        delay_score = min(0.7, delay_min / 180.0) if delay_min > 15.0 else 0.0

        missed_bonus = 0.3 if is_missed_waypoint else 0.0

        return min(1.0, max(dist_score, delay_score) + missed_bonus)

    @classmethod
    def _normalize_telemetry(
        cls,
        telemetry_sig: Optional[SafetySignal],
        gps_sig: Optional[SafetySignal],
    ) -> float:
        degradation = 0.0

        if telemetry_sig and isinstance(telemetry_sig.value, dict):
            val = telemetry_sig.value
            overall = val.get("overall_quality", "good").lower()
            freq_hz = float(val.get("observed_frequency_hz", 50.0))
            completeness = float(val.get("completeness_ratio", 1.0))
            battery = float(val.get("battery_level", 1.0))

            if overall in ("poor", "unreliable", "offline"):
                degradation += 0.6
            elif overall in ("degraded", "moderate"):
                degradation += 0.3

            if freq_hz < 20.0:
                degradation += 0.2
            if completeness < 0.6:
                degradation += 0.2
            if battery < 0.15:  # Battery critical < 15%
                degradation += 0.15

        if gps_sig and isinstance(gps_sig.value, dict):
            val = gps_sig.value
            accuracy = float(val.get("accuracy", 10.0))
            staleness = str(val.get("staleness", "live")).lower()

            if staleness == "stale":
                degradation += 0.4
            elif accuracy > 100.0:
                degradation += 0.3
            elif accuracy > 50.0:
                degradation += 0.15

        return min(1.0, degradation)

    @classmethod
    def _normalize_temporal(
        cls,
        temporal_sig: Optional[SafetySignal],
        curr_time: datetime,
    ) -> float:
        hour = curr_time.hour
        # Night risk profile: Highest between 23:00 and 05:00 (11 PM - 5 AM), moderate between 20:00 - 23:00
        if 23 <= hour or hour <= 4:
            base_temporal = 0.65
        elif 20 <= hour < 23 or 5 <= hour <= 6:
            base_temporal = 0.30
        else:
            base_temporal = 0.05

        if temporal_sig and isinstance(temporal_sig.value, dict):
            val = temporal_sig.value
            is_curfew = bool(val.get("is_curfew_active", False))
            is_isolated_night = bool(val.get("is_isolated_zone", False))
            if is_curfew:
                base_temporal = max(base_temporal, 0.85)
            if is_isolated_night and base_temporal > 0.3:
                base_temporal = min(1.0, base_temporal + 0.25)

        return min(1.0, base_temporal)

    @classmethod
    def _normalize_trip_vulnerability(
        cls,
        trip_sig: Optional[SafetySignal],
        context: Dict[str, Any],
    ) -> float:
        vuln_score = 0.1  # baseline standard traveler

        is_solo = context.get("is_solo_traveler", False)
        has_medical = context.get("has_medical_conditions", False) or bool(context.get("medical_conditions"))
        trip_type = str(context.get("trip_type", "urban")).lower()

        if is_solo:
            vuln_score += 0.20
        if has_medical:
            vuln_score += 0.25
        if trip_type in ("extreme", "trekking", "wilderness", "mountaineering", "remote_expedition"):
            vuln_score += 0.30

        if trip_sig and isinstance(trip_sig.value, dict):
            val = trip_sig.value
            if val.get("is_solo"):
                vuln_score = max(vuln_score, 0.35)
            if val.get("high_risk_expedition"):
                vuln_score = max(vuln_score, 0.60)

        return min(1.0, vuln_score)

    @classmethod
    def _normalize_historical(
        cls,
        history_sig: Optional[SafetySignal],
        context: Dict[str, Any],
    ) -> float:
        hist_score = 0.05

        prior_incidents = int(context.get("prior_incidents_count", 0))
        historical_fp_rate = float(context.get("historical_false_positive_rate", 0.0))
        regional_risk_index = float(context.get("regional_risk_index", 0.1))

        if prior_incidents > 0:
            hist_score += min(0.35, prior_incidents * 0.15)

        hist_score += min(0.40, regional_risk_index * 0.4)

        if history_sig and isinstance(history_sig.value, dict):
            val = history_sig.value
            hist_score = max(hist_score, float(val.get("regional_risk_index", hist_score)))

        return min(1.0, hist_score)
