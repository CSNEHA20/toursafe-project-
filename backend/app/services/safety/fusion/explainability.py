"""
TourSafe Explainability & Decision Support Engine

Generates:
- Feature attributions and percentage contributions
- Top primary risk drivers and mitigating factors
- Natural language operational briefs for authorities & calm guidance for tourists
- Prescriptive decision support actions and dispatch verification checklists
"""

from typing import Any, Dict, List, Optional, Tuple

from ....schemas.safety import (
    ConfidenceAssessment,
    DecisionSupportRecommendation,
    ExplainabilityReport,
    FeatureAttribution,
    NormalizedSafetyFeatures,
    RiskScoreBreakdown,
    SignalCorrelationResult,
)


class ExplainabilityEngine:
    """
    Translates raw fused numbers into explainable insights and actionable decision support.
    """

    @classmethod
    def generate_report(
        cls,
        features: NormalizedSafetyFeatures,
        risk_breakdown: RiskScoreBreakdown,
        correlation: SignalCorrelationResult,
        confidence: ConfidenceAssessment,
        raw_signals: Dict[str, Any],
    ) -> Tuple[ExplainabilityReport, DecisionSupportRecommendation]:
        attributions: List[FeatureAttribution] = []
        drivers: List[str] = []
        mitigators: List[str] = []

        total_risk = max(risk_breakdown.composite_risk_score, 1.0)

        # 1. Evaluate Motion Anomaly
        if features.motion_anomaly_norm > 0.1:
            contrib = features.motion_anomaly_norm * 30.0
            pct = round((contrib / total_risk) * 100.0, 1)
            desc = f"LSTM reconstruction error elevated (norm={features.motion_anomaly_norm:.2f})"
            attributions.append(
                FeatureAttribution(
                    feature_name="Motion Anomaly",
                    contribution_score=round(contrib, 1),
                    percentage=pct,
                    direction="INCREASES_RISK",
                    description=desc,
                )
            )
            if features.motion_anomaly_norm > 0.4:
                drivers.append(f"Persistent motion anomaly detected (+{contrib:.0f} risk)")
        else:
            mitigators.append("Smooth motion dynamics consistent with normal tourist activity")

        # 2. Evaluate Kinematic Shock
        if features.kinematic_shock_norm > 0.2:
            contrib = features.kinematic_shock_norm * 25.0
            pct = round((contrib / total_risk) * 100.0, 1)
            desc = f"High-G acceleration spike or sudden deceleration (shock={features.kinematic_shock_norm:.2f})"
            attributions.append(
                FeatureAttribution(
                    feature_name="Kinematic Shock",
                    contribution_score=round(contrib, 1),
                    percentage=pct,
                    direction="INCREASES_RISK",
                    description=desc,
                )
            )
            if features.kinematic_shock_norm > 0.4:
                drivers.append(f"Acute kinematic impact / deceleration shock (+{contrib:.0f} risk)")

        # 3. Evaluate Geospatial Hazard
        if features.geospatial_hazard_norm > 0.1:
            contrib = features.geospatial_hazard_norm * 28.0
            pct = round((contrib / total_risk) * 100.0, 1)
            desc = f"Proximity or containment within restricted/danger geofence (hazard={features.geospatial_hazard_norm:.2f})"
            attributions.append(
                FeatureAttribution(
                    feature_name="Geospatial Hazard",
                    contribution_score=round(contrib, 1),
                    percentage=pct,
                    direction="INCREASES_RISK",
                    description=desc,
                )
            )
            if features.geospatial_hazard_norm > 0.3:
                drivers.append(f"Tourist positioned inside high-risk geofence zone (+{contrib:.0f} risk)")
        else:
            mitigators.append("Tourist located within designated safe operational zone")

        # 4. Evaluate Itinerary Compliance
        if features.itinerary_deviation_norm > 0.15:
            contrib = features.itinerary_deviation_norm * 16.0
            pct = round((contrib / total_risk) * 100.0, 1)
            desc = f"Divergence from scheduled corridor or schedule delay (dev={features.itinerary_deviation_norm:.2f})"
            attributions.append(
                FeatureAttribution(
                    feature_name="Itinerary Deviation",
                    contribution_score=round(contrib, 1),
                    percentage=pct,
                    direction="INCREASES_RISK",
                    description=desc,
                )
            )
            if features.itinerary_deviation_norm > 0.4:
                drivers.append(f"Significant route divergence from planned itinerary (+{contrib:.0f} risk)")
        else:
            mitigators.append("On-track with planned itinerary and schedule corridor")

        # 5. Evaluate Environmental & Temporal Risk
        if features.temporal_risk_norm > 0.3:
            contrib = features.temporal_risk_norm * 10.0
            pct = round((contrib / total_risk) * 100.0, 1)
            desc = f"Off-hours or nocturnal activity window (temporal={features.temporal_risk_norm:.2f})"
            attributions.append(
                FeatureAttribution(
                    feature_name="Temporal Risk",
                    contribution_score=round(contrib, 1),
                    percentage=pct,
                    direction="INCREASES_RISK",
                    description=desc,
                )
            )
            if features.temporal_risk_norm > 0.5:
                drivers.append("Nocturnal / off-hours travel factor")
        else:
            mitigators.append("Daylight operational window")

        # 6. Evaluate Telemetry Health
        if features.telemetry_degradation_norm > 0.3:
            contrib = features.telemetry_degradation_norm * 10.0
            desc = f"Sensor fidelity or packet rate degraded ({features.telemetry_degradation_norm:.2f})"
            attributions.append(
                FeatureAttribution(
                    feature_name="Telemetry Degradation",
                    contribution_score=round(contrib, 1),
                    percentage=round((contrib / total_risk) * 100.0, 1),
                    direction="INCREASES_RISK",
                    description=desc,
                )
            )
            if features.telemetry_degradation_norm > 0.5:
                drivers.append("Degraded telemetry / intermittent GPS lock")
        else:
            mitigators.append("High telemetry fidelity with continuous sensor synchronization")

        # 7. False Alarm Suppression Mitigating Factor
        if correlation.is_false_alarm_suppressed:
            mitigators.append(f"Contextual dampening applied: {correlation.correlated_pattern} (dampening={correlation.dampening_factor:.2f})")

        # Construct Natural Language Operational Summary for Authorities
        score_val = risk_breakdown.composite_risk_score
        label = risk_breakdown.risk_level_label

        summary_parts = [
            f"Risk Assessment: {label} (Composite Score: {score_val}/100, Confidence: {confidence.confidence_class.value}).",
        ]
        if drivers:
            summary_parts.append(f"Primary Drivers: {'; '.join(drivers[:3])}.")
        if correlation.is_false_alarm_suppressed:
            summary_parts.append(f"Filter Action: {correlation.correlation_notes[0] if correlation.correlation_notes else 'False alarm dampened'}.")
        if mitigators:
            summary_parts.append(f"Mitigating Context: {'; '.join(mitigators[:2])}.")

        nl_summary = " ".join(summary_parts)

        # Construct Calm Tourist Guidance Message
        if score_val < 30.0:
            tourist_guidance = "TourSafe active monitoring is enabled. Your journey is proceeding safely."
        elif score_val < 60.0:
            tourist_guidance = "You are in an area requiring standard awareness. Stay on marked paths and keep your device charged."
        elif score_val < 80.0:
            tourist_guidance = "Caution: Heightened risk detected in your current vicinity. Please check your route map and confirm you are safe."
        else:
            tourist_guidance = "Safety alert triggered. Local support is on standby. If you need immediate assistance, use the Emergency SOS button."

        # -------------------------------------------------------------------
        # Decision Support Recommendations
        # -------------------------------------------------------------------
        checklist: List[str] = []
        advisory: Optional[str] = None
        responder_type: Optional[str] = None

        if score_val >= 80.0 or correlation.correlated_pattern in ("CORROBORATED_VEHICULAR_CRASH", "CORROBORATED_HAZARD_FALL"):
            action = "EMERGENCY_DISPATCH_CONFIRMATION"
            priority = "URGENT"
            responder_type = "emergency_medical_and_police"
            checklist = [
                "Attempt direct telephone voice contact with tourist",
                "Verify live GPS vector and nearest road access points",
                "Alert nearest field responder unit and patrol lead",
                "Review CCTV / local surveillance feeds if in covered zone",
            ]
        elif score_val >= 60.0 or correlation.correlated_pattern == "NIGHT_OFF_ROUTE_ISOLATION":
            action = "PROACTIVE_SAFETY_CHECK"
            priority = "HIGH"
            responder_type = "patrol_officer"
            checklist = [
                "Transmit interactive in-app safety check prompt to tourist",
                "Monitor next 3 telemetry windows for location progression",
                "Notify regional dispatch monitor of watch list addition",
            ]
        elif score_val >= 30.0:
            action = "MONITOR_ELEVATED"
            priority = "MEDIUM"
            checklist = [
                "Track corridor adherence over subsequent 5 minutes",
                "Verify battery level and telemetry stability",
            ]
        else:
            action = "MONITOR_STANDARD"
            priority = "LOW"
            checklist = [
                "Standard background monitoring active",
            ]

        if confidence.confidence_class in ("LOW", "UNKNOWN") or features.telemetry_degradation_norm > 0.4:
            advisory = "Sensor degradation detected. GPS accuracy or packet frequency below optimal fidelity."
            checklist.append("Advisory: Request device reconnect or GPS setting verification if condition persists")

        explainability_report = ExplainabilityReport(
            primary_risk_drivers=drivers,
            mitigating_factors=mitigators,
            feature_attributions=attributions,
            natural_language_summary=nl_summary,
            tourist_guidance=tourist_guidance,
        )

        decision_support = DecisionSupportRecommendation(
            recommended_action=action,
            action_priority=priority,
            verification_checklist=checklist,
            sensor_health_advisory=advisory,
            suggested_responder_type=responder_type,
        )

        return explainability_report, decision_support
