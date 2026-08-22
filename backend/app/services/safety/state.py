"""
TourSafe Safety State Machine & Incident Lifecycle

Explicit State Transitions:
  NORMAL <-> WATCH <-> ELEVATED <-> INCIDENT_CANDIDATE <-> INCIDENT
  INCIDENT -> RECOVERING -> NORMAL
  UNKNOWN <-> [Any State]

Incident Lifecycle:
  OPEN -> ACKNOWLEDGED -> MONITORING -> RESOLVED / CANCELLED
  Incident Deduplication & Cooldown Tracking
"""

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Set, Tuple

from ...schemas.safety import (
    IncidentRecord,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    SafetyDecision,
    SafetyState,
)

logger = logging.getLogger("toursafe.safety.state")


# Explicit valid transitions map
VALID_STATE_TRANSITIONS: Dict[SafetyState, Set[SafetyState]] = {
    SafetyState.NORMAL: {
        SafetyState.NORMAL,
        SafetyState.WATCH,
        SafetyState.ELEVATED,
        SafetyState.UNKNOWN,
        SafetyState.ERROR,
    },
    SafetyState.WATCH: {
        SafetyState.NORMAL,
        SafetyState.WATCH,
        SafetyState.ELEVATED,
        SafetyState.UNKNOWN,
        SafetyState.ERROR,
    },
    SafetyState.ELEVATED: {
        SafetyState.WATCH,
        SafetyState.ELEVATED,
        SafetyState.INCIDENT_CANDIDATE,
        SafetyState.NORMAL,
        SafetyState.UNKNOWN,
        SafetyState.ERROR,
    },
    SafetyState.INCIDENT_CANDIDATE: {
        SafetyState.ELEVATED,
        SafetyState.INCIDENT_CANDIDATE,
        SafetyState.INCIDENT,
        SafetyState.RECOVERING,
        SafetyState.UNKNOWN,
        SafetyState.ERROR,
    },
    SafetyState.INCIDENT: {
        SafetyState.INCIDENT,
        SafetyState.RECOVERING,
        SafetyState.UNKNOWN,
        SafetyState.ERROR,
    },
    SafetyState.RECOVERING: {
        SafetyState.RECOVERING,
        SafetyState.NORMAL,
        SafetyState.WATCH,
        SafetyState.ELEVATED,
        SafetyState.INCIDENT,
        SafetyState.UNKNOWN,
        SafetyState.ERROR,
    },
    SafetyState.UNKNOWN: {
        SafetyState.UNKNOWN,
        SafetyState.NORMAL,
        SafetyState.WATCH,
        SafetyState.ELEVATED,
        SafetyState.INCIDENT_CANDIDATE,
        SafetyState.INCIDENT,
        SafetyState.RECOVERING,
        SafetyState.ERROR,
    },
    SafetyState.ERROR: {
        SafetyState.NORMAL,
        SafetyState.UNKNOWN,
        SafetyState.ERROR,
    },
}

# Valid Incident Transitions
VALID_INCIDENT_TRANSITIONS: Dict[IncidentStatus, Set[IncidentStatus]] = {
    IncidentStatus.OPEN: {
        IncidentStatus.ACKNOWLEDGED,
        IncidentStatus.MONITORING,
        IncidentStatus.RESOLVED,
        IncidentStatus.CANCELLED,
    },
    IncidentStatus.ACKNOWLEDGED: {
        IncidentStatus.MONITORING,
        IncidentStatus.RESOLVED,
        IncidentStatus.CANCELLED,
    },
    IncidentStatus.MONITORING: {
        IncidentStatus.RESOLVED,
        IncidentStatus.CANCELLED,
        IncidentStatus.ACKNOWLEDGED,
    },
    IncidentStatus.RESOLVED: set(),  # Terminal
    IncidentStatus.CANCELLED: set(),  # Terminal
}


class SafetyStateMachine:
    """
    Validates and executes transitions in the safety state machine.
    """

    @staticmethod
    def is_valid_transition(current_state: Any, target_state: Any) -> bool:
        c_val = current_state.value if hasattr(current_state, "value") else str(current_state)
        t_val = target_state.value if hasattr(target_state, "value") else str(target_state)
        for state_enum, allowed_set in VALID_STATE_TRANSITIONS.items():
            if state_enum.value == c_val:
                allowed_vals = {s.value for s in allowed_set}
                return t_val in allowed_vals
        return False

    @classmethod
    def apply_transition(
        cls,
        current_state: SafetyState,
        evaluated_decision: SafetyDecision,
        recovery_started_at: Optional[str] = None,
    ) -> Tuple[SafetyState, Optional[str]]:
        """
        Applies evaluated decision to the state machine.
        Returns: (final_state, updated_recovery_started_at)
        """
        proposed_state = evaluated_decision.state
        now_iso = datetime.now(timezone.utc).isoformat()
        updated_recovery = recovery_started_at

        # If entering RECOVERING for the first time
        if proposed_state == SafetyState.RECOVERING and current_state in (SafetyState.INCIDENT, SafetyState.INCIDENT_CANDIDATE, SafetyState.ELEVATED):
            if not updated_recovery:
                updated_recovery = now_iso

        # If progressing to candidate -> incident
        if current_state == SafetyState.INCIDENT_CANDIDATE and proposed_state == SafetyState.INCIDENT_CANDIDATE:
            # Candidate confirmed on consecutive cycle
            proposed_state = SafetyState.INCIDENT

        # If valid transition, adopt proposed state
        if cls.is_valid_transition(current_state, proposed_state):
            final_state = proposed_state
        else:
            logger.warning(
                "Invalid direct transition requested from %s to %s for tourist %s. Gating transition.",
                current_state,
                proposed_state,
                evaluated_decision.tourist_id,
            )
            # Default to intermediate step
            if proposed_state == SafetyState.INCIDENT and current_state == SafetyState.NORMAL:
                final_state = SafetyState.WATCH
            elif proposed_state == SafetyState.INCIDENT and current_state == SafetyState.WATCH:
                final_state = SafetyState.ELEVATED
            elif proposed_state == SafetyState.INCIDENT and current_state == SafetyState.ELEVATED:
                final_state = SafetyState.INCIDENT_CANDIDATE
            else:
                final_state = current_state

        # Clear recovery timestamp once returned to NORMAL
        if final_state == SafetyState.NORMAL:
            updated_recovery = None

        return final_state, updated_recovery


class IncidentLifecycleManager:
    """
    Manages creation, deduplication, acknowledgement, and resolution of safety incidents.
    """

    @staticmethod
    def can_transition(current_status: Any, target_status: Any) -> bool:
        c_val = current_status.value if hasattr(current_status, "value") else str(current_status)
        t_val = target_status.value if hasattr(target_status, "value") else str(target_status)
        for status_enum, allowed_set in VALID_INCIDENT_TRANSITIONS.items():
            if status_enum.value == c_val:
                allowed_vals = {s.value for s in allowed_set}
                return t_val in allowed_vals
        return False

    @staticmethod
    def create_or_update_incident(
        tourist_id: str,
        session_id: Optional[str],
        decision: SafetyDecision,
        existing_incident: Optional[IncidentRecord] = None,
    ) -> IncidentRecord:
        """
        Deduplicates incidents: updates existing active incident or creates a new one.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # Determine severity based on decision state and quality
        severity = IncidentSeverity.HIGH
        if decision.quality == "POOR":
            severity = IncidentSeverity.MEDIUM
        elif any(r.rule_id == "RULE_A3_HIGH_SEVERITY_ANOMALY" for r in decision.triggered_rules):
            severity = IncidentSeverity.CRITICAL

        if existing_incident and existing_incident.status in (
            IncidentStatus.OPEN,
            IncidentStatus.ACKNOWLEDGED,
            IncidentStatus.MONITORING,
        ):
            # Update existing active incident
            existing_incident.decision_id = decision.decision_id
            existing_incident.reasons = decision.reasons
            existing_incident.signal_summary = decision.signals
            existing_incident.severity = severity
            existing_incident.updated_at = now_iso
            return existing_incident

        # Create brand new incident
        inc_id = f"inc_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{tourist_id[:6]}"
        tle = {
            "event_id": f"tle_{datetime.now(timezone.utc).timestamp()}",
            "incident_id": inc_id,
            "timestamp": now_iso,
            "actor_type": "SYSTEM",
            "actor_id": "safety_engine",
            "action": "incident.created",
            "previous_state": None,
            "new_state": IncidentStatus.OPEN.value,
            "metadata": {"severity": severity.value, "rule_version": decision.rule_version},
            "reason": "; ".join(decision.reasons),
        }
        return IncidentRecord(
            incident_id=inc_id,
            tourist_id=tourist_id,
            session_id=session_id,
            started_at=now_iso,
            status=IncidentStatus.OPEN,
            severity=severity,
            source=IncidentSource.SAFETY_ENGINE,
            decision_id=decision.decision_id,
            rule_version=decision.rule_version,
            reasons=decision.reasons,
            signal_summary=decision.signals,
            timeline=[tle],
            version=1,
            created_at=now_iso,
            updated_at=now_iso,
        )

    @staticmethod
    def acknowledge_incident(
        incident: IncidentRecord,
        authority_id: str,
        notes: Optional[str] = None,
    ) -> IncidentRecord:
        if not IncidentLifecycleManager.can_transition(incident.status, IncidentStatus.ACKNOWLEDGED):
            raise ValueError(f"Cannot acknowledge incident in status '{incident.status}'")

        now_iso = datetime.now(timezone.utc).isoformat()
        incident.status = IncidentStatus.ACKNOWLEDGED
        incident.acknowledged_at = now_iso
        incident.acknowledged_by = authority_id
        if notes:
            incident.notes = f"{incident.notes or ''}\n[Ack]: {notes}".strip()
        incident.updated_at = now_iso
        return incident

    @staticmethod
    def resolve_incident(
        incident: IncidentRecord,
        resolution_reason: str,
        authority_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> IncidentRecord:
        st_val = incident.status.value if hasattr(incident.status, "value") else str(incident.status)
        if not IncidentLifecycleManager.can_transition(incident.status, IncidentStatus.RESOLVED):
            raise ValueError(f"Cannot resolve incident in status '{st_val}'")

        now_iso = datetime.now(timezone.utc).isoformat()
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = now_iso
        log_entry = f"[Resolved]: {resolution_reason}"
        if authority_id:
            log_entry += f" (by {authority_id})"
        if notes:
            log_entry += f" - Notes: {notes}"
        incident.notes = f"{incident.notes or ''}\n{log_entry}".strip()
        incident.updated_at = now_iso
        return incident
