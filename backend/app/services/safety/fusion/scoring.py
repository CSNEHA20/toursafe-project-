"""
TourSafe Multi-Layer Risk Fusion Scoring & Confidence Quantification

Computes:
- Granular sub-category risk scores (Motion, Spatial, Itinerary, Environmental, Vulnerability)
- Contextually dampened Composite Risk Score (0 - 100 scale)
- Comprehensive Confidence Assessment & Uncertainty Quantification
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple

from ....schemas.safety import (
    ConfidenceAssessment,
    ConfidenceClass,
    NormalizedSafetyFeatures,
    RiskScoreBreakdown,
    SignalCorrelationResult,
)
from ..config import safety_config


class RiskFusionScorer:
    """
    Computes multi-layer risk scores and quantified confidence scores.
    """

    # Domain Component Weights (sum = 1.0)
    WEIGHT_MOTION = 0.30
    WEIGHT_SPATIAL = 0.28
    WEIGHT_ITINERARY = 0.16
    WEIGHT_ENVIRONMENTAL = 0.14
    WEIGHT_VULNERABILITY = 0.12

    @classmethod
    def compute_risk_breakdown(
        cls,
        features: NormalizedSafetyFeatures,
        correlation: SignalCorrelationResult,
        previous_composite_score: Optional[float] = None,
    ) -> RiskScoreBreakdown:
        """
        Computes sub-scores and dampened composite risk score.
        """
        # 1. Motion Risk Sub-Score (0-100)
        # Blend persistent anomaly with acute kinematic shock
        motion_raw = (0.55 * features.motion_anomaly_norm + 0.45 * features.kinematic_shock_norm) * 100.0
        motion_score = min(100.0, motion_raw)

        # 2. Spatial / Geospatial Risk Sub-Score (0-100)
        spatial_score = min(100.0, features.geospatial_hazard_norm * 100.0)

        # 3. Itinerary / Route Compliance Risk Sub-Score (0-100)
        itinerary_score = min(100.0, features.itinerary_deviation_norm * 100.0)

        # 4. Environmental / Temporal Risk Sub-Score (0-100)
        env_raw = (0.60 * features.temporal_risk_norm + 0.40 * features.telemetry_degradation_norm) * 100.0
        environmental_score = min(100.0, env_raw)

        # 5. Vulnerability & History Risk Sub-Score (0-100)
        vuln_raw = (0.60 * features.trip_vulnerability_norm + 0.40 * features.historical_risk_norm) * 100.0
        vulnerability_score = min(100.0, vuln_raw)

        # 6. Weighted Base Composite Score
        raw_composite = (
            cls.WEIGHT_MOTION * motion_score
            + cls.WEIGHT_SPATIAL * spatial_score
            + cls.WEIGHT_ITINERARY * itinerary_score
            + cls.WEIGHT_ENVIRONMENTAL * environmental_score
            + cls.WEIGHT_VULNERABILITY * vulnerability_score
        )

        # Compound synergy boost: If both spatial danger and motion shock are high
        if features.geospatial_hazard_norm >= 0.6 and (features.motion_anomaly_norm >= 0.5 or features.kinematic_shock_norm >= 0.6):
            raw_composite = min(100.0, raw_composite * 1.25)

        # Apply correlation dampening factor (e.g. benign highway vibration, dropped phone)
        dampened_composite = raw_composite * correlation.dampening_factor
        composite_score = round(min(100.0, max(0.0, dampened_composite)), 1)

        # Determine Risk Level Label
        if composite_score < 30.0:
            level_label = "SAFE"
        elif composite_score < 60.0:
            level_label = "WATCH"
        elif composite_score < 80.0:
            level_label = "ELEVATED"
        else:
            level_label = "CRITICAL"

        # Determine Trend
        trend = "STABLE"
        if previous_composite_score is not None:
            delta = composite_score - previous_composite_score
            if delta >= 5.0:
                trend = "INCREASING"
            elif delta <= -5.0:
                trend = "DECREASING"

        return RiskScoreBreakdown(
            composite_risk_score=composite_score,
            motion_risk_score=round(motion_score, 1),
            spatial_risk_score=round(spatial_score, 1),
            itinerary_risk_score=round(itinerary_score, 1),
            environmental_risk_score=round(environmental_score, 1),
            vulnerability_risk_score=round(vulnerability_score, 1),
            risk_level_label=level_label,
            risk_trend=trend,
        )

    @classmethod
    def compute_confidence_assessment(
        cls,
        features: NormalizedSafetyFeatures,
        raw_signals_count: int,
        has_gps: bool,
        has_telemetry: bool,
        has_imu: bool,
        avg_signal_age_seconds: float = 0.0,
    ) -> ConfidenceAssessment:
        """
        Quantifies uncertainty and confidence across sensor health, stream sparsity, and signal alignment.
        """
        # 1. Sensor Uncertainty (degraded packets, jitter, poor GPS accuracy)
        sensor_uncertainty = min(1.0, features.telemetry_degradation_norm * 0.9)

        # 2. Sparsity Penalty (penalize missing primary modalities)
        missing_count = 0
        if not has_gps:
            missing_count += 1
        if not has_telemetry:
            missing_count += 1
        if not has_imu:
            missing_count += 1

        sparsity_penalty = min(1.0, missing_count * 0.35)

        # 3. Cross-Signal Conflict Penalty (e.g. extreme shock in safe baseline or high speed with stationary flag)
        conflict_penalty = 0.0
        if features.kinematic_shock_norm > 0.7 and features.geospatial_hazard_norm == 0.0 and features.motion_anomaly_norm < 0.2:
            conflict_penalty = 0.35
        elif features.motion_anomaly_norm > 0.8 and features.telemetry_degradation_norm > 0.7:
            conflict_penalty = 0.25

        # 4. Freshness Penalty
        freshness_penalty = min(0.4, (avg_signal_age_seconds / safety_config.signal_expiry_seconds) * 0.4)

        # Calculate final confidence score [0.0 - 1.0]
        deductions = (
            0.55 * sensor_uncertainty
            + 0.30 * sparsity_penalty
            + 0.15 * conflict_penalty
            + 0.10 * freshness_penalty
        )
        conf_score = max(0.0, min(1.0, 1.0 - deductions))

        # Categorize into ConfidenceClass
        if sensor_uncertainty >= 0.6 or conf_score < 0.55:
            conf_class = ConfidenceClass.LOW if conf_score > 0.15 else ConfidenceClass.UNKNOWN
        elif conf_score >= 0.78 and sensor_uncertainty < 0.30:
            conf_class = ConfidenceClass.HIGH
        else:
            conf_class = ConfidenceClass.MEDIUM

        return ConfidenceAssessment(
            confidence_score=round(conf_score, 3),
            confidence_class=conf_class,
            sensor_uncertainty=round(sensor_uncertainty, 3),
            sparsity_penalty=round(sparsity_penalty, 3),
            cross_signal_conflict=round(conflict_penalty, 3),
            freshness_penalty=round(freshness_penalty, 3),
        )
