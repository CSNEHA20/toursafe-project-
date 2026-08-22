"""
TourSafe Central Safety Orchestration & Multi-Signal Risk Fusion Engine

Coordinates:
- Ingestion and normalization of multi-signal inputs (GPS, Zone, Anomaly, Telemetry, Tracking, Context)
- Deterministic rule evaluation via versioned safety rules (safety-rules-v1)
- State machine evaluation (NORMAL <-> WATCH <-> ELEVATED <-> INCIDENT_CANDIDATE <-> INCIDENT <-> RECOVERING <-> UNKNOWN)
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
    SafetyDecision,
    SafetySignal,
    SafetyState,
)
from .config import safety_config
from .events import safety_event_publisher
from .redis_state import safety_redis_state
from .repository import safety_repository
from .rules import rule_engine
from .state import IncidentLifecycleManager, SafetyStateMachine

logger = logging.getLogger("toursafe.safety.engine")


class SafetyOrchestrationEngine:
    """
    Central safety orchestrator for TourSafe.
    """

    async def ingest_signal(
        self,
        signal: SafetySignal,
        user_id: Optional[str] = None,
    ) -> SafetyDecision:
        """
        Main entry point: Ingests a new safety signal, evaluates the multi-signal rule engine,
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

        # 3. Retrieve all fresh active signals for tourist
        all_signals = await safety_redis_state.get_active_signals(tourist_id)

        # 4. Evaluate deterministic safety rules
        evaluated_decision = rule_engine.evaluate_signals(
            tourist_id=tourist_id,
            session_id=session_id,
            previous_state=current_state,
            active_signals=all_signals,
            recovery_started_at=recovery_started_at,
        )

        # 5. Apply state machine transition rules
        final_state, updated_recovery = SafetyStateMachine.apply_transition(
            current_state=current_state,
            evaluated_decision=evaluated_decision,
            recovery_started_at=recovery_started_at,
        )

        evaluated_decision.state = final_state

        # 6. Check for state transition
        state_changed = (final_state != current_state)
        now_iso = datetime.now(timezone.utc).isoformat()

        # 7. Persist immutable decision to MongoDB (for all state changes or periodically)
        await safety_repository.record_decision(evaluated_decision)

        # 8. Manage Incidents
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
                # Check if we should fetch existing incident metadata
                active_incident = await safety_repository.get_incident_by_id(existing_incident_id)

        # 9. Update Active State in Redis
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
        )
        await safety_redis_state.set_active_state(updated_active_state)

        # 10. Broadcast realtime event if state changed or critical
        if state_changed or final_state in (SafetyState.INCIDENT, SafetyState.INCIDENT_CANDIDATE):
            await safety_event_publisher.publish_state_changed(evaluated_decision, user_id=user_id)

        return evaluated_decision

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
