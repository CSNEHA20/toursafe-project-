"""
TourSafe Deterministic Safety Rule Engine (safety-rules-v1)

Explicit, versioned, auditable safety rules categorized into:
- Category A: Anomaly
- Category B: Geofence
- Category C: GPS
- Category D: Telemetry
- Category E: Persistence & Recovery
- Category F: Context & Multi-Signal Correlation
- Category G: Signal Quality & UNKNOWN Gating
- Category H: Risk Fusion & False-Positive Reduction

Every decision includes human-readable explainable reasons, triggered rule IDs,
and full MultiSignalRiskAssessment metadata.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple

from ...schemas.safety import (
    ConfidenceClass,
    MultiSignalRiskAssessment,
    SafetyDecision,
    SafetySignal,
    SafetyState,
    SignalQuality,
    SignalType,
    TriggeredRule,
)
from .config import safety_config
from .fusion import risk_fusion_engine
from .signals import is_signal_fresh, parse_timestamp_iso

logger = logging.getLogger("toursafe.safety.rules")


class RuleEngine:
    """
    Evaluates fresh safety signals against deterministic versioned safety rules and multi-signal risk fusion.
    """

    def __init__(self, rule_version: str = "safety-rules-v1"):
        self.rule_version = rule_version

    def evaluate_signals(
        self,
        tourist_id: str,
        session_id: Optional[str],
        previous_state: SafetyState,
        active_signals: List[SafetySignal],
        recovery_started_at: Optional[str] = None,
        tourist_context: Optional[Dict[str, Any]] = None,
        previous_assessment: Optional[MultiSignalRiskAssessment] = None,
        now: Optional[datetime] = None,
    ) -> SafetyDecision:
        """
        Deterministic rule evaluation and multi-signal risk fusion on aggregated active safety signals.
        """
        curr_time = now or datetime.now(timezone.utc)
        curr_iso = curr_time.isoformat()

        # 1. Filter active signals for freshness
        fresh_signals = [s for s in active_signals if is_signal_fresh(s, curr_time)]

        # Extract subsystem states from fresh signals
        anomaly_sig: Optional[SafetySignal] = None
        gps_sig: Optional[SafetySignal] = None
        zone_sigs: List[SafetySignal] = []
        telemetry_sig: Optional[SafetySignal] = None
        tracking_sig: Optional[SafetySignal] = None
        itinerary_sig: Optional[SafetySignal] = None

        for s in fresh_signals:
            if s.signal_type in (SignalType.ANOMALY_DETECTED, SignalType.ANOMALY_CLEARED):
                anomaly_sig = s
            elif s.signal_type in (SignalType.GPS_LOCATION_UPDATE, SignalType.GPS_STALE, SignalType.GPS_UNCERTAIN):
                gps_sig = s
            elif s.signal_type in (SignalType.ZONE_ENTERED, SignalType.ZONE_EXITED, SignalType.ZONE_DWELL):
                if isinstance(s.value, dict) and s.value.get("membership_state") in ("inside", "uncertain", "approaching"):
                    zone_sigs.append(s)
            elif s.signal_type in (SignalType.TELEMETRY_GOOD, SignalType.TELEMETRY_DEGRADED, SignalType.TELEMETRY_OFFLINE):
                telemetry_sig = s
            elif s.signal_type in (SignalType.TRACKING_ACTIVE, SignalType.TRACKING_STOPPED):
                tracking_sig = s
            elif s.signal_type == SignalType.ITINERARY_DEVIATION:
                itinerary_sig = s

        triggered_rules: List[TriggeredRule] = []
        reasons: List[str] = []

        # 2. Execute Advanced Multi-Signal Risk Fusion Engine
        risk_assessment = risk_fusion_engine.evaluate_risk_fusion(
            tourist_id=tourist_id,
            session_id=session_id,
            active_signals=fresh_signals,
            tourist_context=tourist_context,
            previous_assessment=previous_assessment,
            now=curr_time,
        )

        composite_risk = risk_assessment.risk_breakdown.composite_risk_score
        correlation = risk_assessment.correlation
        confidence = risk_assessment.confidence.confidence_class

        # 3. Check for UNKNOWN state: No fresh GPS, no fresh telemetry, or tracking stopped
        has_fresh_gps = gps_sig is not None and gps_sig.signal_type != SignalType.GPS_STALE
        has_fresh_telemetry = telemetry_sig is not None and telemetry_sig.signal_type != SignalType.TELEMETRY_OFFLINE
        is_tracking_active = tracking_sig is None or tracking_sig.signal_type == SignalType.TRACKING_ACTIVE

        # Category G: Signal Quality & UNKNOWN Gating
        if (not has_fresh_gps and not has_fresh_telemetry) or not is_tracking_active:
            reason_txt = "Insufficient real-time telemetry or tracking stopped; position and safety status cannot be verified"
            triggered_rules.append(
                TriggeredRule(
                    rule_id="RULE_G1_NO_DATA_UNKNOWN",
                    rule_name="No Real-time Telemetry Data",
                    category="Category G: Signal Quality",
                    contributed_state=SafetyState.UNKNOWN,
                    reason=reason_txt,
                    confidence_weight=1.0,
                    matched_signals=[s.signal_id for s in fresh_signals],
                )
            )
            reasons.append(reason_txt)
            return SafetyDecision(
                tourist_id=tourist_id,
                session_id=session_id,
                timestamp=curr_iso,
                state=SafetyState.UNKNOWN,
                previous_state=previous_state,
                rule_version=self.rule_version,
                triggered_rules=triggered_rules,
                reasons=reasons,
                signals={s.signal_type.value: s.value for s in fresh_signals},
                quality=SignalQuality.UNKNOWN,
                confidence_class=ConfidenceClass.UNKNOWN,
                risk_score=composite_risk,
                risk_assessment=risk_assessment,
            )

        # 4. Assess Signal Quality & Confidence Class
        quality = SignalQuality.GOOD
        rule_confidence = ConfidenceClass.HIGH

        if gps_sig and gps_sig.quality in (SignalQuality.POOR, SignalQuality.DEGRADED):
            quality = SignalQuality.DEGRADED
            rule_confidence = ConfidenceClass.MEDIUM
            r_text = f"GPS accuracy degraded ({gps_sig.metadata.get('accuracy_meters', 0)}m)"
            triggered_rules.append(
                TriggeredRule(
                    rule_id="RULE_C2_GPS_UNCERTAIN",
                    rule_name="Degraded GPS Accuracy",
                    category="Category C: GPS",
                    contributed_state=SafetyState.WATCH,
                    reason=r_text,
                    confidence_weight=0.6,
                    matched_signals=[gps_sig.signal_id],
                )
            )
            reasons.append(r_text)

        if telemetry_sig and telemetry_sig.quality in (SignalQuality.POOR, SignalQuality.DEGRADED):
            quality = SignalQuality.DEGRADED
            if rule_confidence == ConfidenceClass.MEDIUM:
                rule_confidence = ConfidenceClass.LOW
            else:
                rule_confidence = ConfidenceClass.MEDIUM
            r_text = f"Telemetry packet quality degraded ({telemetry_sig.value.get('overall_quality', 'unknown') if isinstance(telemetry_sig.value, dict) else 'degraded'})"
            triggered_rules.append(
                TriggeredRule(
                    rule_id="RULE_D1_TELEMETRY_DEGRADED",
                    rule_name="Degraded Telemetry Quality",
                    category="Category D: Telemetry",
                    contributed_state=SafetyState.WATCH,
                    reason=r_text,
                    confidence_weight=0.6,
                    matched_signals=[telemetry_sig.signal_id],
                )
            )
            reasons.append(r_text)

        confidence_ranks = {ConfidenceClass.HIGH: 3, ConfidenceClass.MEDIUM: 2, ConfidenceClass.LOW: 1, ConfidenceClass.UNKNOWN: 0}
        fused_conf = risk_assessment.confidence.confidence_class
        confidence = fused_conf if confidence_ranks.get(fused_conf, 0) < confidence_ranks.get(rule_confidence, 3) else rule_confidence

        # 5. Evaluate Anomaly Signals (Category A)
        is_anomalous = False
        anomaly_consecutive = 0
        anomaly_score = 0.0
        anomaly_thresh = 0.5

        if anomaly_sig and anomaly_sig.signal_type == SignalType.ANOMALY_DETECTED:
            is_anomalous = True
            val = anomaly_sig.value if isinstance(anomaly_sig.value, dict) else {}
            anomaly_consecutive = val.get("consecutive_windows", 1)
            anomaly_score = float(val.get("score", 0.0))
            anomaly_thresh = float(val.get("threshold", 0.5))

            if correlation.is_false_alarm_suppressed:
                r_text = f"Motion anomaly filtered by correlation engine ({correlation.correlated_pattern})"
                triggered_rules.append(
                    TriggeredRule(
                        rule_id="RULE_H1_FALSE_ALARM_DAMPENED",
                        rule_name="False Alarm Suppressed via Correlation",
                        category="Category H: Risk Fusion",
                        contributed_state=SafetyState.WATCH,
                        reason=r_text,
                        confidence_weight=0.4,
                        matched_signals=[anomaly_sig.signal_id],
                    )
                )
                reasons.append(r_text)
            elif anomaly_consecutive >= safety_config.anomaly_high_persistence_windows and anomaly_score >= (anomaly_thresh * safety_config.anomaly_high_score_multiplier):
                r_text = f"High-severity persistent motion anomaly (score={anomaly_score:.2f}, {anomaly_consecutive} windows)"
                triggered_rules.append(
                    TriggeredRule(
                        rule_id="RULE_A3_HIGH_SEVERITY_ANOMALY",
                        rule_name="High Severity Persistent Motion Anomaly",
                        category="Category A: Anomaly",
                        contributed_state=SafetyState.INCIDENT_CANDIDATE,
                        reason=r_text,
                        confidence_weight=1.0,
                        matched_signals=[anomaly_sig.signal_id],
                    )
                )
                reasons.append(r_text)
            elif anomaly_consecutive >= safety_config.anomaly_min_persistence_windows:
                r_text = f"Persistent motion anomaly detected ({anomaly_consecutive} consecutive windows, score={anomaly_score:.2f})"
                triggered_rules.append(
                    TriggeredRule(
                        rule_id="RULE_A2_PERSISTENT_ANOMALY",
                        rule_name="Persistent Motion Anomaly",
                        category="Category A: Anomaly",
                        contributed_state=SafetyState.ELEVATED,
                        reason=r_text,
                        confidence_weight=0.8,
                        matched_signals=[anomaly_sig.signal_id],
                    )
                )
                reasons.append(r_text)
            else:
                r_text = f"Transient motion anomaly detected (score={anomaly_score:.2f})"
                triggered_rules.append(
                    TriggeredRule(
                        rule_id="RULE_A1_TRANSIENT_ANOMALY",
                        rule_name="Transient Motion Anomaly",
                        category="Category A: Anomaly",
                        contributed_state=SafetyState.WATCH,
                        reason=r_text,
                        confidence_weight=0.5,
                        matched_signals=[anomaly_sig.signal_id],
                    )
                )
                reasons.append(r_text)

        # 6. Evaluate Geofence Zones (Category B)
        highest_zone_risk = "safe"
        highest_zone_rank = 1

        for z in zone_sigs:
            if not isinstance(z.value, dict):
                continue
            z_risk = str(z.value.get("risk_level", "low")).lower()
            z_name = z.value.get("zone_name", "Unknown Zone")
            z_rank = safety_config.zone_risk_levels.get(z_risk, 1)

            if z_rank > highest_zone_rank:
                highest_zone_rank = z_rank
                highest_zone_risk = z_risk

            if z_rank >= 4:  # Danger / Critical
                r_text = f"Tourist inside danger zone '{z_name}' (risk={z_risk})"
                triggered_rules.append(
                    TriggeredRule(
                        rule_id="RULE_B3_DANGER_ZONE",
                        rule_name="Danger Zone Containment",
                        category="Category B: Geofence",
                        contributed_state=SafetyState.ELEVATED,
                        reason=r_text,
                        confidence_weight=0.9,
                        matched_signals=[z.signal_id],
                    )
                )
                reasons.append(r_text)
            elif z_rank == 3:  # Restricted
                r_text = f"Tourist inside restricted zone '{z_name}'"
                triggered_rules.append(
                    TriggeredRule(
                        rule_id="RULE_B2_RESTRICTED_ZONE",
                        rule_name="Restricted Zone Containment",
                        category="Category B: Geofence",
                        contributed_state=SafetyState.ELEVATED,
                        reason=r_text,
                        confidence_weight=0.7,
                        matched_signals=[z.signal_id],
                    )
                )
                reasons.append(r_text)
            elif z_rank == 2:  # Caution
                r_text = f"Tourist inside caution zone '{z_name}'"
                triggered_rules.append(
                    TriggeredRule(
                        rule_id="RULE_B1_CAUTION_ZONE",
                        rule_name="Caution Zone Containment",
                        category="Category B: Geofence",
                        contributed_state=SafetyState.WATCH,
                        reason=r_text,
                        confidence_weight=0.4,
                        matched_signals=[z.signal_id],
                    )
                )
                reasons.append(r_text)

            # Dwell duration check
            dwell_sec = z.value.get("dwell_duration_seconds")
            if dwell_sec and dwell_sec >= 300.0 and z_rank >= 3:
                r_text = f"Prolonged dwell ({int(dwell_sec)}s) in high-risk zone '{z_name}'"
                triggered_rules.append(
                    TriggeredRule(
                        rule_id="RULE_B4_DWELL_EXCEEDED",
                        rule_name="High Risk Zone Dwell Exceeded",
                        category="Category B: Geofence",
                        contributed_state=SafetyState.ELEVATED,
                        reason=r_text,
                        confidence_weight=0.8,
                        matched_signals=[z.signal_id],
                    )
                )
                reasons.append(r_text)

        # 7. Evaluate Corroborated Multi-Signal Patterns (Category F & H)
        if correlation.correlated_pattern in ("CORROBORATED_VEHICULAR_CRASH", "CORROBORATED_HAZARD_FALL"):
            r_text = f"High-confidence corroborated hazard signature: {correlation.correlated_pattern}"
            matched = [s.signal_id for s in fresh_signals]
            triggered_rules.append(
                TriggeredRule(
                    rule_id="RULE_H2_CORROBORATED_EMERGENCY_PATTERN",
                    rule_name="Corroborated High-Risk Pattern",
                    category="Category H: Risk Fusion",
                    contributed_state=SafetyState.INCIDENT_CANDIDATE,
                    reason=r_text,
                    confidence_weight=1.0,
                    matched_signals=matched,
                )
            )
            reasons.append(r_text)
        elif is_anomalous and highest_zone_rank >= 4 and anomaly_consecutive >= safety_config.anomaly_min_persistence_windows and not correlation.is_false_alarm_suppressed:
            r_text = "Multi-signal corroboration: persistent motion anomaly inside high-risk danger zone"
            matched = [anomaly_sig.signal_id] + [z.signal_id for z in zone_sigs]
            triggered_rules.append(
                TriggeredRule(
                    rule_id="RULE_F2_PERSISTENT_ANOMALY_IN_DANGER_ZONE",
                    rule_name="Persistent Anomaly in Danger Zone",
                    category="Category F: Context & Corroboration",
                    contributed_state=SafetyState.INCIDENT_CANDIDATE,
                    reason=r_text,
                    confidence_weight=1.0,
                    matched_signals=matched,
                )
            )
            reasons.append(r_text)
        elif is_anomalous and highest_zone_rank >= 3 and not correlation.is_false_alarm_suppressed:
            r_text = "Corroborating motion anomaly within restricted/caution zone"
            matched = [anomaly_sig.signal_id] + [z.signal_id for z in zone_sigs]
            triggered_rules.append(
                TriggeredRule(
                    rule_id="RULE_F1_ANOMALY_IN_RESTRICTED_ZONE",
                    rule_name="Anomaly in Restricted Zone",
                    category="Category F: Context & Corroboration",
                    contributed_state=SafetyState.ELEVATED,
                    reason=r_text,
                    confidence_weight=0.8,
                    matched_signals=matched,
                )
            )
            reasons.append(r_text)

        if itinerary_sig and isinstance(itinerary_sig.value, dict):
            dist_val = itinerary_sig.value.get("distance_meters", 0.0)
            if not correlation.is_false_alarm_suppressed and dist_val > 50.0:
                r_text = f"Itinerary route deviation ({dist_val:.0f}m from planned route)"
                triggered_rules.append(
                    TriggeredRule(
                        rule_id="RULE_F3_ITINERARY_DEVIATION",
                        rule_name="Itinerary Route Deviation",
                        category="Category F: Context & Corroboration",
                        contributed_state=SafetyState.WATCH,
                        reason=r_text,
                        confidence_weight=0.3,
                        matched_signals=[itinerary_sig.signal_id],
                    )
                )
                reasons.append(r_text)

        # 8. Evaluate Fused Composite Risk Score Thresholds (Category H)
        if composite_risk >= safety_config.risk_threshold_candidate and not correlation.is_false_alarm_suppressed:
            r_text = f"Fused composite risk score critical ({composite_risk:.1f}/100)"
            triggered_rules.append(
                TriggeredRule(
                    rule_id="RULE_H4_FUSED_COMPOSITE_RISK_CRITICAL",
                    rule_name="Critical Composite Risk Score",
                    category="Category H: Risk Fusion",
                    contributed_state=SafetyState.INCIDENT_CANDIDATE,
                    reason=r_text,
                    confidence_weight=0.95,
                    matched_signals=[s.signal_id for s in fresh_signals],
                )
            )
            reasons.append(r_text)
        elif composite_risk >= safety_config.risk_threshold_elevated and not correlation.is_false_alarm_suppressed:
            r_text = f"Fused composite risk score elevated ({composite_risk:.1f}/100)"
            triggered_rules.append(
                TriggeredRule(
                    rule_id="RULE_H3_FUSED_COMPOSITE_RISK_ELEVATED",
                    rule_name="Elevated Composite Risk Score",
                    category="Category H: Risk Fusion",
                    contributed_state=SafetyState.ELEVATED,
                    reason=r_text,
                    confidence_weight=0.85,
                    matched_signals=[s.signal_id for s in fresh_signals],
                )
            )
            reasons.append(r_text)

        # 9. Determine Target Candidate State from Triggered Rules
        state_ranks = {
            SafetyState.NORMAL: 1,
            SafetyState.WATCH: 2,
            SafetyState.ELEVATED: 3,
            SafetyState.INCIDENT_CANDIDATE: 4,
            SafetyState.INCIDENT: 5,
            SafetyState.RECOVERING: 2,
            SafetyState.UNKNOWN: 0,
        }

        substantive_rules = [
            r for r in triggered_rules
            if r.rule_id not in ("RULE_C2_GPS_UNCERTAIN", "RULE_D1_TELEMETRY_DEGRADED", "RULE_F3_ITINERARY_DEVIATION", "RULE_H1_FALSE_ALARM_DAMPENED")
        ]

        if not substantive_rules:
            # All safety-critical signals are normal
            prev_val = previous_state.value if hasattr(previous_state, "value") else str(previous_state)
            if prev_val in (SafetyState.INCIDENT.value, SafetyState.INCIDENT_CANDIDATE.value, SafetyState.ELEVATED.value, SafetyState.RECOVERING.value):
                # Category E: Recovery Gate
                recov_dt = parse_timestamp_iso(recovery_started_at) if recovery_started_at else curr_time
                recov_age = max(0.0, (curr_time - recov_dt).total_seconds())

                if recov_age < safety_config.recovery_cooldown_seconds:
                    r_text = f"Signals normalized; in recovery observation period ({int(recov_age)}s/{int(safety_config.recovery_cooldown_seconds)}s)"
                    triggered_rules.append(
                        TriggeredRule(
                            rule_id="RULE_E1_RECOVERY_IN_PROGRESS",
                            rule_name="Recovery In Progress",
                            category="Category E: Persistence & Recovery",
                            contributed_state=SafetyState.RECOVERING,
                            reason=r_text,
                            confidence_weight=1.0,
                            matched_signals=[],
                        )
                    )
                    reasons.append(r_text)
                    target_state = SafetyState.RECOVERING
                else:
                    r_text = "Stable normal state verified; recovery completed"
                    triggered_rules.append(
                        TriggeredRule(
                            rule_id="RULE_E2_RECOVERY_STABLE",
                            rule_name="Recovery Completed to Normal",
                            category="Category E: Persistence & Recovery",
                            contributed_state=SafetyState.NORMAL,
                            reason=r_text,
                            confidence_weight=1.0,
                            matched_signals=[],
                        )
                    )
                    reasons.append(r_text)
                    target_state = SafetyState.NORMAL
            else:
                if triggered_rules:
                    target_state = SafetyState.WATCH
                else:
                    reasons.append("All safety signals normal (GPS verified, telemetry healthy, safe zone, no motion anomalies)")
                    target_state = SafetyState.NORMAL
        else:
            highest_state = SafetyState.NORMAL
            for r in substantive_rules:
                if state_ranks.get(r.contributed_state, 0) > state_ranks.get(highest_state, 0):
                    highest_state = r.contributed_state

            target_state = highest_state

        # Quality Gating: If confidence is LOW, cap maximum state at ELEVATED unless crash confirmed
        if confidence == ConfidenceClass.LOW and state_ranks.get(target_state, 0) > state_ranks.get(SafetyState.ELEVATED, 0):
            if correlation.correlated_pattern not in ("CORROBORATED_VEHICULAR_CRASH", "CORROBORATED_HAZARD_FALL"):
                r_text = "Incident candidate gated to ELEVATED due to low sensor confidence / degraded telemetry"
                reasons.append(r_text)
                target_state = SafetyState.ELEVATED

        # Collect model versions & zone metadata
        model_versions = {}
        if anomaly_sig and isinstance(anomaly_sig.metadata, dict) and "model_version" in anomaly_sig.metadata:
            model_versions["lstm_autoencoder"] = anomaly_sig.metadata["model_version"]

        zone_versions = {}
        for z in zone_sigs:
            if isinstance(z.value, dict):
                zid = z.value.get("zone_id", "unknown")
                zone_versions[zid] = z.value.get("risk_level", "unknown")

        return SafetyDecision(
            tourist_id=tourist_id,
            session_id=session_id,
            timestamp=curr_iso,
            state=target_state,
            previous_state=previous_state,
            rule_version=self.rule_version,
            triggered_rules=triggered_rules,
            reasons=reasons,
            signals={s.signal_type.value: s.value for s in fresh_signals},
            quality=quality,
            confidence_class=confidence,
            model_versions=model_versions,
            zone_versions=zone_versions,
            risk_score=composite_risk,
            risk_assessment=risk_assessment,
        )


rule_engine = RuleEngine(rule_version=safety_config.rule_version)
