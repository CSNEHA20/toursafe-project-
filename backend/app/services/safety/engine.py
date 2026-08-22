"""
TourSafe Central Safety Orchestration & Multi-Signal Risk Fusion Engine

Coordinates:
- Ingestion and normalization of multi-signal inputs (GPS, Zone, Anomaly, Telemetry, Tracking, Context)
- Deterministic rule evaluation via versioned safety rules (safety-rules-v1) and RiskFusionEngine
- State machine evaluation (NORMAL <-> WATCH <-> ELEVATED <-> INCIDENT_CANDIDATE <-> INCIDENT <-> RECOVERING <-> UNKNOWN)
- False-positive reduction, correlation signatures, and tourist safety check-in loops
- Incident deduplication and lifecycle management
- Active state caching in Redis and durable immutable audit logging in MongoDB
- Realtime WebSocket event broadcasting to authority and tourist channels
- Zero automated SOS / emergency dispatch (Strict Scope)
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple

from ...schemas.safety import (
    ActiveSafetyState,
    IncidentRecord,
    IncidentStatus,
    MultiSignalRiskAssessment,
    SafetyCheckResponseRequest,
    SafetyCheckResponseResult,
    SafetyDecision,
    SafetySignal,
    SafetyState,
)
from .config import safety_config
from .events import safety_event_publisher
from .fusion import risk_fusion_engine
from .redis_state import safety_redis_state
from .repository import safety_repository
from .rules import rule_engine
from .state import IncidentLifecycleManager, SafetyStateMachine

logger = logging.getLogger("toursafe.safety.engine")

# Transient cache for active safety check requests and responses
_tourist_check_contexts: Dict[str, Dict[str, Any]] = {}


class SafetyOrchestrationEngine:
    """
    Central safety orchestrator for TourSafe.
    """

    async def ingest_signal(
        self,
        signal: SafetySignal,
        user_id: Optional[str] = None,
        context_override: Optional[Dict[str, Any]] = None,
    ) -> SafetyDecision:
        """
        Main entry point: Ingests a new safety signal, evaluates the multi-signal rule engine & risk fusion,
        executes state transitions, updates Redis/MongoDB, and emits realtime WebSocket events.
        """
        tourist_id = signal.tourist_id
        session_id = signal.session_id

        # 1. Update active signal cache in Redis
        await safety_redis_state.update_active_signal(signal)

        # 2. Retrieve current active state (or initialize to UNKNOWN)
        active_state = await safety_redis_state.get_active_state(tourist_id)
        current_state = active_state.current_state if active_state else SafetyState.UNKNOWN
        recovery_started_at = active_state.recovery_started_at if active_state else None
        existing_incident_id = active_state.active_incident_id if active_state else None
        prev_assessment = active_state.risk_assessment if active_state else None

        # 3. Retrieve all fresh active signals for tourist
        all_signals = await safety_redis_state.get_active_signals(tourist_id)

        # 4. Assemble Tourist Context (including check-in responses)
        tourist_ctx = dict(_tourist_check_contexts.get(tourist_id, {}))
        if context_override:
            tourist_ctx.update(context_override)

        # Check timestamp of last safe confirmation
        if "last_safe_check_time" in tourist_ctx:
            age = (datetime.now(timezone.utc) - tourist_ctx["last_safe_check_time"]).total_seconds()
            tourist_ctx["recent_safe_check_confirmed"] = (age <= 600.0)
            tourist_ctx["safe_check_age_seconds"] = age

        # 5. Evaluate deterministic safety rules & multi-signal risk fusion
        evaluated_decision = rule_engine.evaluate_signals(
            tourist_id=tourist_id,
            session_id=session_id,
            previous_state=current_state,
            active_signals=all_signals,
            recovery_started_at=recovery_started_at,
            tourist_context=tourist_ctx,
            previous_assessment=prev_assessment,
        )

        # 6. Apply state machine transition rules
        final_state, updated_recovery = SafetyStateMachine.apply_transition(
            current_state=current_state,
            evaluated_decision=evaluated_decision,
            recovery_started_at=recovery_started_at,
        )

        evaluated_decision.state = final_state

        # 7. Check for state transition
        state_changed = (final_state != current_state)
        now_iso = datetime.now(timezone.utc).isoformat()

        # 8. Persist immutable decision to MongoDB
        await safety_repository.record_decision(evaluated_decision)

        # 9. Manage Incidents
        active_incident: Optional[IncidentRecord] = None
        if final_state == SafetyState.INCIDENT:
            # Check for existing active incident in Mongo
            existing_inc = await safety_repository.get_active_incident(tourist_id)
            is_new_incident = (existing_inc is None)
            active_incident = IncidentLifecycleManager.create_or_update_incident(
                tourist_id=tourist_id,
                session_id=session_id,
                decision=evaluated_decision,
                existing_incident=existing_inc,
            )
            await safety_repository.upsert_incident(active_incident)
            existing_incident_id = active_incident.incident_id

            if is_new_incident:
                await safety_event_publisher.publish_incident_created(active_incident)
            else:
                await safety_event_publisher.publish_incident_updated(active_incident)
        else:
            if existing_incident_id:
                active_incident = await safety_repository.get_incident_by_id(existing_incident_id)

        # 10. Update Active State in Redis with Fused Risk Assessment
        updated_active_state = ActiveSafetyState(
            tourist_id=tourist_id,
            current_state=final_state,
            previous_state=current_state,
            decision_id=evaluated_decision.decision_id,
            started_at=active_state.started_at if (active_state and not state_changed) else now_iso,
            last_update=now_iso,
            rule_version=safety_config.rule_version,
            confidence_class=evaluated_decision.confidence_class,
            active_reasons=evaluated_decision.reasons,
            active_signals_summary=evaluated_decision.signals,
            active_incident_id=existing_incident_id,
            recovery_started_at=updated_recovery,
            risk_score=evaluated_decision.risk_score,
            risk_assessment=evaluated_decision.risk_assessment,
        )
        await safety_redis_state.set_active_state(updated_active_state)

        # 11. Trigger Proactive Safety Check Prompt if Recommended
        if (
            evaluated_decision.risk_assessment
            and evaluated_decision.risk_assessment.decision_support.recommended_action == "PROACTIVE_SAFETY_CHECK"
            and not tourist_ctx.get("recent_safe_check_confirmed", False)
        ):
            await safety_event_publisher.publish_safety_check_requested(
                tourist_id=tourist_id,
                prompt_message=evaluated_decision.risk_assessment.explainability.tourist_guidance,
                assessment_id=evaluated_decision.risk_assessment.assessment_id,
            )

        # 12. Broadcast Realtime WebSocket Events
        if state_changed or final_state in (SafetyState.INCIDENT, SafetyState.INCIDENT_CANDIDATE):
            await safety_event_publisher.publish_state_changed(evaluated_decision, user_id=user_id)
        elif evaluated_decision.risk_assessment:
            await safety_event_publisher.publish_risk_assessment_updated(evaluated_decision.risk_assessment)

        return evaluated_decision

    async def handle_safety_check_response(
        self,
        tourist_id: str,
        payload: SafetyCheckResponseRequest,
    ) -> SafetyCheckResponseResult:
        """
        Processes a tourist's response to an interactive safety check prompt ("Confirm I'm Safe" / "Need Help").
        Directly adjusts contextual dampening or elevates assistance.
        """
        now = datetime.now(timezone.utc)
        resp_type = payload.response_type.upper()

        if resp_type in ("SAFE_CONFIRMED", "FALSE_ALARM"):
            _tourist_check_contexts[tourist_id] = {
                "recent_safe_check_confirmed": True,
                "last_safe_check_time": now,
                "safe_check_age_seconds": 0.0,
                "user_note": payload.user_note,
                "battery_level": payload.battery_level,
            }

            # Retrieve active state and re-evaluate with active safe dampening
            active_state = await safety_redis_state.get_active_state(tourist_id)
            all_signals = await safety_redis_state.get_active_signals(tourist_id)

            if active_state and all_signals:
                re_decision = rule_engine.evaluate_signals(
                    tourist_id=tourist_id,
                    session_id=None,
                    previous_state=active_state.current_state,
                    active_signals=all_signals,
                    tourist_context=_tourist_check_contexts[tourist_id],
                )
                final_state, updated_recov = SafetyStateMachine.apply_transition(
                    current_state=active_state.current_state,
                    evaluated_decision=re_decision,
                    recovery_started_at=active_state.recovery_started_at,
                )
                re_decision.state = final_state

                active_state.current_state = final_state
                active_state.risk_score = re_decision.risk_score
                active_state.risk_assessment = re_decision.risk_assessment
                active_state.last_update = now.isoformat()
                await safety_redis_state.set_active_state(active_state)
                await safety_event_publisher.publish_state_changed(re_decision)

            # Broadcast response to authority
            await safety_event_publisher.publish_safety_check_responded(
                tourist_id=tourist_id,
                response_data={
                    "response_type": resp_type,
                    "user_note": payload.user_note,
                    "battery_level": payload.battery_level,
                    "status": "CONFIRMED_SAFE",
                },
            )

            return SafetyCheckResponseResult(
                success=True,
                message="Thank you! Your safety confirmation has been registered with TourSafe.",
                updated_state=active_state.current_state if active_state else SafetyState.NORMAL,
                risk_score=active_state.risk_score if active_state and active_state.risk_score is not None else 10.0,
                guidance="Active monitoring continues. Have a safe journey!",
            )

        elif resp_type == "ASSISTANCE_REQUESTED":
            _tourist_check_contexts[tourist_id] = {
                "recent_safe_check_confirmed": False,
                "assistance_requested": True,
                "user_note": payload.user_note,
            }

            # Broadcast response to authority operations immediately
            await safety_event_publisher.publish_safety_check_responded(
                tourist_id=tourist_id,
                response_data={
                    "response_type": resp_type,
                    "user_note": payload.user_note,
                    "battery_level": payload.battery_level,
                    "status": "ASSISTANCE_REQUESTED",
                    "priority": "URGENT",
                },
            )

            active_state = await safety_redis_state.get_active_state(tourist_id)
            return SafetyCheckResponseResult(
                success=True,
                message="Assistance request received. Authority command center has been notified.",
                updated_state=active_state.current_state if active_state else SafetyState.ELEVATED,
                risk_score=active_state.risk_score if active_state and active_state.risk_score is not None else 85.0,
                guidance="Please remain in a safe location. If in immediate danger, trigger the SOS button.",
            )

        return SafetyCheckResponseResult(
            success=False,
            message=f"Unknown response type '{payload.response_type}'",
            updated_state=SafetyState.NORMAL,
            risk_score=0.0,
            guidance="",
        )

    async def evaluate_simulated_signals(
        self,
        tourist_id: str,
        signals: List[SafetySignal],
        context: Optional[Dict[str, Any]] = None,
    ) -> MultiSignalRiskAssessment:
        """
        Executes on-demand risk fusion evaluation on a simulated or historical signal set
        without mutating live Redis active state.
        """
        return risk_fusion_engine.evaluate_risk_fusion(
            tourist_id=tourist_id,
            session_id=None,
            active_signals=signals,
            tourist_context=context,
        )

    async def get_tourist_safety_snapshot(self, tourist_id: str) -> Optional[ActiveSafetyState]:
        """Retrieves active safety state snapshot for tourist."""
        return await safety_redis_state.get_active_state(tourist_id)

    async def acknowledge_incident(
        self,
        incident_id: str,
        authority_id: str,
        notes: Optional[str] = None,
    ) -> IncidentRecord:
        """Authority acknowledges an open incident."""
        incident = await safety_repository.get_incident_by_id(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        updated = IncidentLifecycleManager.acknowledge_incident(incident, authority_id=authority_id, notes=notes)
        await safety_repository.upsert_incident(updated)
        await safety_event_publisher.publish_incident_updated(updated)
        return updated

    async def resolve_incident(
        self,
        incident_id: str,
        resolution_reason: str,
        authority_id: str,
        notes: Optional[str] = None,
    ) -> IncidentRecord:
        """Authority resolves an incident with a mandatory explanation."""
        incident = await safety_repository.get_incident_by_id(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        updated = IncidentLifecycleManager.resolve_incident(
            incident=incident,
            resolution_reason=resolution_reason,
            authority_id=authority_id,
            notes=notes,
        )
        await safety_repository.upsert_incident(updated)
        await safety_event_publisher.publish_incident_resolved(updated)

        # Clear active_incident_id in Redis state
        active_state = await safety_redis_state.get_active_state(incident.tourist_id)
        if active_state and active_state.active_incident_id == incident_id:
            active_state.active_incident_id = None
            await safety_redis_state.set_active_state(active_state)

        return updated


safety_orchestrator = SafetyOrchestrationEngine()
