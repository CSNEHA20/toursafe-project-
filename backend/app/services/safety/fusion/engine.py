"""
TourSafe Central Risk Fusion Engine

Coordinates normalization, cross-signal correlation, multi-layer risk scoring,
confidence assessment, explainability generation, and decision support recommendations.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from ....schemas.safety import (
    MultiSignalRiskAssessment,
    SafetySignal,
    SignalType,
)
from .correlation import SignalCorrelationEngine
from .explainability import ExplainabilityEngine
from .normalization import SignalNormalizer
from .scoring import RiskFusionScorer

logger = logging.getLogger("toursafe.safety.fusion.engine")


class RiskFusionEngine:
    """
    Main entry point for multi-signal safety intelligence & risk fusion.
    """

    @classmethod
    def evaluate_risk_fusion(
        cls,
        tourist_id: str,
        session_id: Optional[str],
        active_signals: List[SafetySignal],
        tourist_context: Optional[Dict[str, Any]] = None,
        previous_assessment: Optional[MultiSignalRiskAssessment] = None,
        now: Optional[datetime] = None,
    ) -> MultiSignalRiskAssessment:
        curr_time = now or datetime.now(timezone.utc)
        curr_iso = curr_time.isoformat()

        # 1. Normalize Multi-Domain Signals into Standardized Features
        normalized_features = SignalNormalizer.normalize_signals(
            active_signals=active_signals,
            tourist_context=tourist_context,
            now=curr_time,
        )

        # Build raw signal map for quick lookup
        raw_map = {s.signal_type.value: s.value for s in active_signals}

        # 2. Evaluate Signal Cross-Correlation & False Positive Reductions
        correlation_result = SignalCorrelationEngine.evaluate_correlation(
            features=normalized_features,
            raw_signals=raw_map,
            tourist_context=tourist_context,
            now=curr_time,
        )

        # 3. Compute Granular Sub-Scores & Composite Risk Score
        prev_score = (
            previous_assessment.risk_breakdown.composite_risk_score
            if previous_assessment
            else None
        )
        risk_breakdown = RiskFusionScorer.compute_risk_breakdown(
            features=normalized_features,
            correlation=correlation_result,
            previous_composite_score=prev_score,
        )

        # 4. Quantify Confidence & Sensor Uncertainty
        has_gps = any(s.signal_type in (SignalType.GPS_LOCATION_UPDATE, SignalType.GPS_UNCERTAIN) for s in active_signals)
        has_telemetry = any(s.signal_type in (SignalType.TELEMETRY_GOOD, SignalType.TELEMETRY_DEGRADED) for s in active_signals)
        has_imu = any(s.signal_type in (SignalType.ANOMALY_DETECTED, SignalType.ANOMALY_CLEARED) for s in active_signals)

        confidence_assessment = RiskFusionScorer.compute_confidence_assessment(
            features=normalized_features,
            raw_signals_count=len(active_signals),
            has_gps=has_gps,
            has_telemetry=has_telemetry,
            has_imu=has_imu,
            avg_signal_age_seconds=0.0,
        )

        # 5. Generate Explainability Report & Prescriptive Decision Support
        explainability, decision_support = ExplainabilityEngine.generate_report(
            features=normalized_features,
            risk_breakdown=risk_breakdown,
            correlation=correlation_result,
            confidence=confidence_assessment,
            raw_signals=raw_map,
        )

        return MultiSignalRiskAssessment(
            tourist_id=tourist_id,
            session_id=session_id,
            timestamp=curr_iso,
            normalized_features=normalized_features,
            risk_breakdown=risk_breakdown,
            correlation=correlation_result,
            confidence=confidence_assessment,
            explainability=explainability,
            decision_support=decision_support,
            raw_signals_count=len(active_signals),
        )


risk_fusion_engine = RiskFusionEngine()
