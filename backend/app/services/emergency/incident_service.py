"""
TourSafe Incident Command Orchestration Service

Central operational management for safety incidents with optimistic locking,
strict state machine transition matrices, immutable timeline event generation,
responder coordination, and audit tracking.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from ...core import database as db_core


def get_database():
    return db_core.get_database()
from ...schemas.emergency import (
    IncidentMetricsResponse,
    IncidentNoteRecord,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    NotificationChannel,
    PolicyTriggerType,
    ResolutionCategory,
    TimelineEventRecord,
)
from ...schemas.safety import IncidentRecord
from ..safety.events import safety_event_publisher
from .incident_channel_service import incident_channel_service
from .messaging_service import messaging_service
from .notifications import notification_service
from .responder_service import responder_service

logger = logging.getLogger("toursafe.emergency.incident")

# Strict Incident State Transition Matrix
ALLOWED_INCIDENT_TRANSITIONS: Dict[IncidentStatus, Set[IncidentStatus]] = {
    IncidentStatus.OPEN: {
        IncidentStatus.ACKNOWLEDGED,
        IncidentStatus.ASSESSING,
        IncidentStatus.CANCELLED,
    },
    IncidentStatus.ACKNOWLEDGED: {
        IncidentStatus.ASSESSING,
        IncidentStatus.ASSIGNED,
        IncidentStatus.RESPONDING,
        IncidentStatus.ESCALATED,
        IncidentStatus.RESOLVED,
        IncidentStatus.CANCELLED,
    },
    IncidentStatus.ASSESSING: {
        IncidentStatus.ASSIGNED,
        IncidentStatus.RESPONDING,
        IncidentStatus.ESCALATED,
        IncidentStatus.RESOLVED,
        IncidentStatus.CANCELLED,
    },
    IncidentStatus.ASSIGNED: {
        IncidentStatus.RESPONDING,
        IncidentStatus.ESCALATED,
        IncidentStatus.RESOLVED,
        IncidentStatus.CANCELLED,
    },
    IncidentStatus.RESPONDING: {
        IncidentStatus.ESCALATED,
        IncidentStatus.RESOLVED,
        IncidentStatus.CANCELLED,
    },
    IncidentStatus.MONITORING: {
        IncidentStatus.ACKNOWLEDGED,
        IncidentStatus.ASSESSING,
        IncidentStatus.ASSIGNED,
        IncidentStatus.RESPONDING,
        IncidentStatus.RESOLVED,
        IncidentStatus.CANCELLED,
    },
    IncidentStatus.ESCALATED: {
        IncidentStatus.ASSIGNED,
        IncidentStatus.RESPONDING,
        IncidentStatus.RESOLVED,
        IncidentStatus.CANCELLED,
    },
    IncidentStatus.RESOLVED: {
        IncidentStatus.CLOSED,
    },
    IncidentStatus.CANCELLED: {
        IncidentStatus.CLOSED,
    },
    IncidentStatus.CLOSED: set(),  # Terminal state. Cannot reopen.
}


class IncidentCommandService:
    """
    Central incident command lifecycle orchestration service.
    """

    def is_transition_allowed(self, current: Any, target: Any) -> bool:
        c_name = current.value if hasattr(current, "value") else str(current)
        t_name = target.value if hasattr(target, "value") else str(target)
        for state_enum, allowed_set in ALLOWED_INCIDENT_TRANSITIONS.items():
            if state_enum.value == c_name:
                return t_name in {s.value for s in allowed_set}
        return False

    async def get_incident(self, incident_id: str) -> Optional[IncidentRecord]:
        db = get_database()
        doc = await db.incidents.find_one({"incident_id": incident_id})
        if not doc:
            return None
        return IncidentRecord(**doc)

    async def get_active_incident_for_tourist(self, tourist_id: str) -> Optional[IncidentRecord]:
        db = get_database()
        doc = await db.incidents.find_one({
            "tourist_id": tourist_id,
            "status": {
                "$in": [
                    IncidentStatus.OPEN.value,
                    IncidentStatus.ACKNOWLEDGED.value,
                    IncidentStatus.ASSESSING.value,
                    IncidentStatus.ASSIGNED.value,
                    IncidentStatus.RESPONDING.value,
                    IncidentStatus.MONITORING.value,
                    IncidentStatus.ESCALATED.value,
                ]
            },
        })
        if not doc:
            return None
        return IncidentRecord(**doc)

    async def create_incident(
        self,
        tourist_id: str,
        source: IncidentSource,
        severity: IncidentSeverity = IncidentSeverity.HIGH,
        session_id: Optional[str] = None,
        decision_id: str = "none",
        rule_version: str = "safety-rules-v1",
        reasons: Optional[List[str]] = None,
        signal_summary: Optional[Dict[str, Any]] = None,
        location_data: Optional[Dict[str, Any]] = None,
        actor_id: str = "system",
        actor_type: str = "SYSTEM",
    ) -> IncidentRecord:
        """
        Creates a new incident with initial timeline record.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        incident_id = f"inc_{uuid.uuid4().hex[:12]}"
        reasons_list = reasons or []
        signals = signal_summary or {}

        init_timeline = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type=actor_type,
            actor_id=actor_id,
            action="incident.created",
            previous_state=None,
            new_state=IncidentStatus.OPEN.value,
            metadata={"source": source.value, "severity": severity.value, "location": location_data},
            reason="; ".join(reasons_list) if reasons_list else "Incident created",
        )

        incident = IncidentRecord(
            incident_id=incident_id,
            tourist_id=tourist_id,
            session_id=session_id,
            started_at=now_iso,
            status=IncidentStatus.OPEN,
            severity=severity,
            source=source,
            decision_id=decision_id,
            rule_version=rule_version,
            reasons=reasons_list,
            signal_summary=signals,
            location_data=location_data,
            timeline=[init_timeline.model_dump()],
            version=1,
            created_at=now_iso,
            updated_at=now_iso,
        )

        db = get_database()
        await db.incidents.insert_one(incident.model_dump())

        # Notify emergency contacts if high severity and enabled by policy
        if severity in (IncidentSeverity.HIGH, IncidentSeverity.CRITICAL):
            await notification_service.notify_emergency_contacts_for_incident(
                incident_id=incident.incident_id,
                tourist_id=tourist_id,
                severity=severity.value,
            )

        # Broadcast realtime event
        await safety_event_publisher.publish_incident_created(incident)

        # Trigger response plan orchestration
        try:
            from .response_orchestrator import response_orchestrator
            trigger_type = PolicyTriggerType.MANUAL_SOS if source == IncidentSource.MANUAL_SOS else PolicyTriggerType.SAFETY_STATE
            await response_orchestrator.initiate_response_plan(
                incident_id=incident.incident_id,
                trigger_type=trigger_type,
                trigger_metadata={"source": source.value, "severity": severity.value},
            )
        except Exception as orch_err:
            logger.warning("Failed to initiate response plan for %s: %s", incident.incident_id, orch_err)

        return incident

    async def acknowledge_incident(
        self,
        incident_id: str,
        authority_id: str,
        notes: Optional[str] = None,
        expected_version: Optional[int] = None,
    ) -> IncidentRecord:
        incident = await self.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        if expected_version is not None and incident.version != expected_version:
            raise ValueError(f"Optimistic lock conflict: expected version {expected_version}, found {incident.version}")

        if not self.is_transition_allowed(incident.status, IncidentStatus.ACKNOWLEDGED):
            raise ValueError(f"Cannot transition incident from '{incident.status.value}' to 'ACKNOWLEDGED'")

        now_iso = datetime.now(timezone.utc).isoformat()
        prev_status = incident.status.value
        incident.status = IncidentStatus.ACKNOWLEDGED
        incident.acknowledged_at = now_iso
        incident.acknowledged_by = authority_id
        incident.updated_at = now_iso
        incident.version += 1

        if notes:
            incident.notes = f"{incident.notes or ''}\n[Ack]: {notes}".strip()
            note_rec = IncidentNoteRecord(
                incident_id=incident_id,
                author_id=authority_id,
                author_role="authority",
                timestamp=now_iso,
                content=f"[Acknowledge]: {notes}",
            )
            incident.notes_list.append(note_rec.model_dump())

        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type="AUTHORITY",
            actor_id=authority_id,
            action="incident.acknowledged",
            previous_state=prev_status,
            new_state=IncidentStatus.ACKNOWLEDGED.value,
            reason=notes or "Authority acknowledged incident",
        )
        incident.timeline.append(tle.model_dump())

        db = get_database()
        await db.incidents.replace_one({"incident_id": incident_id}, incident.model_dump())
        await safety_event_publisher.publish_incident_acknowledged(incident)
        return incident

    async def assess_incident(
        self,
        incident_id: str,
        authority_id: str,
        severity: Optional[IncidentSeverity] = None,
        notes: Optional[str] = None,
        expected_version: Optional[int] = None,
    ) -> IncidentRecord:
        incident = await self.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        if expected_version is not None and incident.version != expected_version:
            raise ValueError(f"Optimistic lock conflict: expected version {expected_version}, found {incident.version}")

        if not self.is_transition_allowed(incident.status, IncidentStatus.ASSESSING):
            raise ValueError(f"Cannot transition incident from '{incident.status.value}' to 'ASSESSING'")

        now_iso = datetime.now(timezone.utc).isoformat()
        prev_status = incident.status.value
        prev_severity = incident.severity.value
        incident.status = IncidentStatus.ASSESSING
        if severity:
            incident.severity = severity
        incident.updated_at = now_iso
        incident.version += 1

        if notes:
            note_rec = IncidentNoteRecord(
                incident_id=incident_id,
                author_id=authority_id,
                author_role="authority",
                timestamp=now_iso,
                content=f"[Assessment]: {notes}",
            )
            incident.notes_list.append(note_rec.model_dump())

        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type="AUTHORITY",
            actor_id=authority_id,
            action="incident.assessing",
            previous_state=prev_status,
            new_state=IncidentStatus.ASSESSING.value,
            metadata={"new_severity": incident.severity.value, "previous_severity": prev_severity},
            reason=notes or "Authority conducting active situation assessment",
        )
        incident.timeline.append(tle.model_dump())

        db = get_database()
        await db.incidents.replace_one({"incident_id": incident_id}, incident.model_dump())
        await safety_event_publisher.publish_incident_assessing(incident)
        if severity and severity.value != prev_severity:
            await safety_event_publisher.publish_incident_severity_changed(incident, prev_severity)
        return incident

    async def assign_responder(
        self,
        incident_id: str,
        authority_id: str,
        responder_id: str,
        unit_id: Optional[str] = None,
        notes: Optional[str] = None,
        expected_version: Optional[int] = None,
    ) -> IncidentRecord:
        incident = await self.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        if expected_version is not None and incident.version != expected_version:
            raise ValueError(f"Optimistic lock conflict: expected version {expected_version}, found {incident.version}")

        if not self.is_transition_allowed(incident.status, IncidentStatus.ASSIGNED):
            raise ValueError(f"Cannot transition incident from '{incident.status.value}' to 'ASSIGNED'")

        # Verify responder exists
        responder = await responder_service.get_responder(responder_id)
        if not responder:
            raise ValueError(f"Responder '{responder_id}' not found")

        now_iso = datetime.now(timezone.utc).isoformat()
        prev_status = incident.status.value

        # Update responder in responder collection
        await responder_service.assign_to_incident(responder_id, incident_id)

        incident.status = IncidentStatus.ASSIGNED
        incident.assigned_to = responder_id
        incident.assigned_unit = unit_id or responder.unit_id
        incident.responder_type = responder.type.value if hasattr(responder.type, "value") else str(responder.type)
        incident.updated_at = now_iso
        incident.version += 1

        if notes:
            note_rec = IncidentNoteRecord(
                incident_id=incident_id,
                author_id=authority_id,
                author_role="authority",
                timestamp=now_iso,
                content=f"[Assignment]: Assigned to {responder.name} ({incident.responder_type}). Notes: {notes}",
            )
            incident.notes_list.append(note_rec.model_dump())

        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type="AUTHORITY",
            actor_id=authority_id,
            action="incident.assigned",
            previous_state=prev_status,
            new_state=IncidentStatus.ASSIGNED.value,
            metadata={
                "responder_id": responder_id,
                "responder_name": responder.name,
                "responder_type": incident.responder_type,
                "unit_id": incident.assigned_unit,
            },
            reason=notes or f"Assigned to {responder.name}",
        )
        incident.timeline.append(tle.model_dump())

        db = get_database()
        await db.incidents.replace_one({"incident_id": incident_id}, incident.model_dump())
        await safety_event_publisher.publish_incident_assigned(incident)
        return incident

    async def start_response(
        self,
        incident_id: str,
        actor_id: str,
        notes: Optional[str] = None,
        estimated_arrival_minutes: Optional[int] = None,
        expected_version: Optional[int] = None,
    ) -> IncidentRecord:
        incident = await self.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        if expected_version is not None and incident.version != expected_version:
            raise ValueError(f"Optimistic lock conflict: expected version {expected_version}, found {incident.version}")

        if not self.is_transition_allowed(incident.status, IncidentStatus.RESPONDING):
            raise ValueError(f"Cannot transition incident from '{incident.status.value}' to 'RESPONDING'")

        now_iso = datetime.now(timezone.utc).isoformat()
        prev_status = incident.status.value
        incident.status = IncidentStatus.RESPONDING
        incident.updated_at = now_iso
        incident.version += 1

        if notes:
            note_rec = IncidentNoteRecord(
                incident_id=incident_id,
                author_id=actor_id,
                author_role="responder",
                timestamp=now_iso,
                content=f"[Response Started]: {notes}",
            )
            incident.notes_list.append(note_rec.model_dump())

        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type="RESPONDER",
            actor_id=actor_id,
            action="incident.response.started",
            previous_state=prev_status,
            new_state=IncidentStatus.RESPONDING.value,
            metadata={"estimated_arrival_minutes": estimated_arrival_minutes},
            reason=notes or "Responder is en route / actively engaging",
        )
        incident.timeline.append(tle.model_dump())

        db = get_database()
        await db.incidents.replace_one({"incident_id": incident_id}, incident.model_dump())
        await safety_event_publisher.publish_incident_response_started(incident)
        return incident

    async def manual_escalate(
        self,
        incident_id: str,
        authority_id: str,
        reason: str,
        target_severity: Optional[IncidentSeverity] = None,
        notes: Optional[str] = None,
        expected_version: Optional[int] = None,
    ) -> IncidentRecord:
        incident = await self.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        if expected_version is not None and incident.version != expected_version:
            raise ValueError(f"Optimistic lock conflict: expected version {expected_version}, found {incident.version}")

        if not self.is_transition_allowed(incident.status, IncidentStatus.ESCALATED):
            raise ValueError(f"Cannot transition incident from '{incident.status.value}' to 'ESCALATED'")

        now_iso = datetime.now(timezone.utc).isoformat()
        prev_status = incident.status.value
        prev_severity = incident.severity.value
        new_severity = target_severity or IncidentSeverity.CRITICAL

        incident.status = IncidentStatus.ESCALATED
        incident.severity = new_severity
        incident.escalation_stage += 1
        incident.updated_at = now_iso
        incident.version += 1

        esc_entry = {
            "idempotency_key": f"{incident_id}:manual_{incident.escalation_stage}:{now_iso}",
            "stage": incident.escalation_stage,
            "stage_name": "Manual Authority Escalation",
            "triggered_at": now_iso,
            "reason": reason,
            "author_id": authority_id,
            "target_severity": new_severity.value,
        }
        incident.escalation_history.append(esc_entry)

        if notes:
            note_rec = IncidentNoteRecord(
                incident_id=incident_id,
                author_id=authority_id,
                author_role="authority",
                timestamp=now_iso,
                content=f"[Escalation]: {reason} - {notes}",
            )
            incident.notes_list.append(note_rec.model_dump())

        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type="AUTHORITY",
            actor_id=authority_id,
            action="incident.escalated",
            previous_state=prev_status,
            new_state=IncidentStatus.ESCALATED.value,
            metadata={"new_severity": new_severity.value, "reason": reason},
            reason=reason,
        )
        incident.timeline.append(tle.model_dump())

        db = get_database()
        await db.incidents.replace_one({"incident_id": incident_id}, incident.model_dump())
        await safety_event_publisher.publish_incident_escalated(incident)
        if new_severity.value != prev_severity:
            await safety_event_publisher.publish_incident_severity_changed(incident, prev_severity)

        # Broadcast authoritative system message in incident channel
        try:
            from ...schemas.emergency import MessagePriority
            await messaging_service.send_system_message(
                incident_id=incident_id,
                content=f"Incident escalated to {new_severity.value}. Reason: {reason}",
                priority=MessagePriority.CRITICAL,
            )
        except Exception as e:
            logger.warning("Failed to send escalation system message: %s", e)

        return incident

    async def add_incident_note(
        self,
        incident_id: str,
        author_id: str,
        author_role: str,
        content: str,
        author_name: Optional[str] = None,
    ) -> IncidentNoteRecord:
        incident = await self.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        now_iso = datetime.now(timezone.utc).isoformat()
        note = IncidentNoteRecord(
            incident_id=incident_id,
            author_id=author_id,
            author_role=author_role,
            author_name=author_name,
            timestamp=now_iso,
            content=content,
        )

        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type=author_role.upper(),
            actor_id=author_id,
            action="incident.note.added",
            metadata={"author_name": author_name},
            reason=f"Note: {content[:80]}...",
        )

        db = get_database()
        await db.incidents.update_one(
            {"incident_id": incident_id},
            {
                "$push": {
                    "notes_list": note.model_dump(),
                    "timeline": tle.model_dump(),
                },
                "$set": {"updated_at": now_iso},
                "$inc": {"version": 1},
            },
        )
        await safety_event_publisher.publish_incident_note_added(incident_id, note.model_dump())
        return note

    async def update_location(self, incident_id: str, location_dict: Dict[str, Any]) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        db = get_database()
        await db.incidents.update_one(
            {"incident_id": incident_id},
            {
                "$set": {
                    "location_data": location_dict,
                    "updated_at": now_iso,
                },
                "$inc": {"version": 1},
            },
        )
        await safety_event_publisher.publish_incident_location_updated(incident_id, location_dict)

    async def resolve_incident(
        self,
        incident_id: str,
        authority_id: str,
        resolution_reason: str,
        resolution_category: ResolutionCategory = ResolutionCategory.TOURIST_SAFE,
        notes: Optional[str] = None,
        expected_version: Optional[int] = None,
    ) -> IncidentRecord:
        incident = await self.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        if expected_version is not None and incident.version != expected_version:
            raise ValueError(f"Optimistic lock conflict: expected version {expected_version}, found {incident.version}")

        if not self.is_transition_allowed(incident.status, IncidentStatus.RESOLVED):
            raise ValueError(f"Cannot transition incident from '{incident.status.value}' to 'RESOLVED'")

        now_iso = datetime.now(timezone.utc).isoformat()
        prev_status = incident.status.value

        # Release responder if assigned
        if incident.assigned_to:
            await responder_service.release_from_incident(incident.assigned_to)

        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = now_iso
        incident.resolution_category = resolution_category.value if hasattr(resolution_category, "value") else str(resolution_category)
        incident.resolution_reason = resolution_reason
        incident.updated_at = now_iso
        incident.version += 1

        if notes:
            note_rec = IncidentNoteRecord(
                incident_id=incident_id,
                author_id=authority_id,
                author_role="authority",
                timestamp=now_iso,
                content=f"[Resolution]: {resolution_reason} ({incident.resolution_category}). Notes: {notes}",
            )
            incident.notes_list.append(note_rec.model_dump())

        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type="AUTHORITY",
            actor_id=authority_id,
            action="incident.resolved",
            previous_state=prev_status,
            new_state=IncidentStatus.RESOLVED.value,
            metadata={"category": incident.resolution_category, "reason": resolution_reason},
            reason=resolution_reason,
        )
        incident.timeline.append(tle.model_dump())

        db = get_database()
        await db.incidents.replace_one({"incident_id": incident_id}, incident.model_dump())
        await safety_event_publisher.publish_incident_resolved(incident)

        # Notify response orchestrator
        try:
            from .response_orchestrator import response_orchestrator
            await response_orchestrator.handle_incident_resolved(
                incident_id=incident_id,
                actor_id=authority_id,
                resolution_data={"category": incident.resolution_category, "reason": resolution_reason},
            )
        except Exception as res_err:
            logger.warning("Failed to notify orchestrator of resolution for %s: %s", incident_id, res_err)

        return incident

    async def cancel_incident(
        self,
        incident_id: str,
        actor_id: str,
        actor_type: str,
        cancellation_reason: str,
        is_false_alarm: bool = False,
        notes: Optional[str] = None,
        expected_version: Optional[int] = None,
    ) -> IncidentRecord:
        incident = await self.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        if expected_version is not None and incident.version != expected_version:
            raise ValueError(f"Optimistic lock conflict: expected version {expected_version}, found {incident.version}")

        if not self.is_transition_allowed(incident.status, IncidentStatus.CANCELLED):
            raise ValueError(f"Cannot transition incident from '{incident.status.value}' to 'CANCELLED'")

        now_iso = datetime.now(timezone.utc).isoformat()
        prev_status = incident.status.value

        if incident.assigned_to:
            await responder_service.release_from_incident(incident.assigned_to)

        incident.status = IncidentStatus.CANCELLED
        incident.cancellation_reason = cancellation_reason
        if is_false_alarm:
            incident.resolution_category = ResolutionCategory.FALSE_ALARM.value
        incident.updated_at = now_iso
        incident.version += 1

        if notes:
            note_rec = IncidentNoteRecord(
                incident_id=incident_id,
                author_id=actor_id,
                author_role=actor_type.lower(),
                timestamp=now_iso,
                content=f"[Cancellation]: {cancellation_reason}. Notes: {notes}",
            )
            incident.notes_list.append(note_rec.model_dump())

        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type=actor_type.upper(),
            actor_id=actor_id,
            action="incident.cancelled",
            previous_state=prev_status,
            new_state=IncidentStatus.CANCELLED.value,
            metadata={"is_false_alarm": is_false_alarm},
            reason=cancellation_reason,
        )
        incident.timeline.append(tle.model_dump())

        db = get_database()
        await db.incidents.replace_one({"incident_id": incident_id}, incident.model_dump())
        await safety_event_publisher.publish_incident_cancelled(incident)

        # Notify response orchestrator
        try:
            from .response_orchestrator import response_orchestrator
            await response_orchestrator.handle_incident_cancelled(
                incident_id=incident_id,
                actor_id=actor_id,
                reason=cancellation_reason,
            )
        except Exception as canc_err:
            logger.warning("Failed to notify orchestrator of cancellation for %s: %s", incident_id, canc_err)

        return incident

    async def close_incident(
        self,
        incident_id: str,
        authority_id: str,
        notes: Optional[str] = None,
        expected_version: Optional[int] = None,
    ) -> IncidentRecord:
        incident = await self.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        if expected_version is not None and incident.version != expected_version:
            raise ValueError(f"Optimistic lock conflict: expected version {expected_version}, found {incident.version}")

        if not self.is_transition_allowed(incident.status, IncidentStatus.CLOSED):
            raise ValueError(f"Cannot transition incident from '{incident.status.value}' to 'CLOSED'. Must be RESOLVED or CANCELLED first.")

        now_iso = datetime.now(timezone.utc).isoformat()
        prev_status = incident.status.value

        incident.status = IncidentStatus.CLOSED
        incident.closed_at = now_iso
        incident.closed_by = authority_id
        incident.updated_at = now_iso
        incident.version += 1

        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type="AUTHORITY",
            actor_id=authority_id,
            action="incident.closed",
            previous_state=prev_status,
            new_state=IncidentStatus.CLOSED.value,
            reason=notes or "Incident formally closed and archived",
        )
        incident.timeline.append(tle.model_dump())

        db = get_database()
        await db.incidents.replace_one({"incident_id": incident_id}, incident.model_dump())
        await safety_event_publisher.publish_incident_closed(incident)

        # Close incident communication channel and emit system event
        try:
            await incident_channel_service.close_channel(incident_id)
            await messaging_service.send_system_message(
                incident_id=incident_id,
                content="Incident formally closed and archived. Channel restricted to read-only.",
            )
        except Exception as e:
            logger.warning("Failed to close incident channel on incident close: %s", e)

        return incident

    async def list_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        source: Optional[str] = None,
        tourist_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        limit: int = 50,
        page: int = 1,
        search: Optional[str] = None,
    ) -> Tuple[List[IncidentRecord], int]:
        db = get_database()
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status
        if severity:
            query["severity"] = severity
        if source:
            query["source"] = source
        if tourist_id:
            query["tourist_id"] = tourist_id
        if assigned_to:
            query["assigned_to"] = assigned_to
        if search:
            query["$or"] = [
                {"incident_id": {"$regex": search, "$options": "i"}},
                {"tourist_id": {"$regex": search, "$options": "i"}},
                {"reasons": {"$regex": search, "$options": "i"}},
            ]

        skip = (page - 1) * limit
        cursor = db.incidents.find(query).sort("started_at", -1).skip(skip).limit(limit)
        items = []
        async for doc in cursor:
            items.append(IncidentRecord(**doc))

        total = await db.incidents.count_documents(query)
        return items, total

    async def get_metrics(self) -> IncidentMetricsResponse:
        db = get_database()
        cursor = db.incidents.find({})
        all_incidents = []
        async for doc in cursor:
            all_incidents.append(IncidentRecord(**doc))

        total = len(all_incidents)
        open_cnt = sum(1 for i in all_incidents if i.status == IncidentStatus.OPEN)
        ack_cnt = sum(1 for i in all_incidents if i.status == IncidentStatus.ACKNOWLEDGED)
        resp_cnt = sum(1 for i in all_incidents if i.status == IncidentStatus.RESPONDING)
        esc_cnt = sum(1 for i in all_incidents if i.status == IncidentStatus.ESCALATED)
        res_cnt = sum(1 for i in all_incidents if i.status == IncidentStatus.RESOLVED)
        closed_cnt = sum(1 for i in all_incidents if i.status == IncidentStatus.CLOSED)
        cancel_cnt = sum(1 for i in all_incidents if i.status == IncidentStatus.CANCELLED)

        # Durations
        ack_durations = []
        resolve_durations = []
        assign_durations = []
        false_alarms = 0

        for inc in all_incidents:
            start_dt = datetime.fromisoformat(inc.started_at.replace("Z", "+00:00"))
            if inc.acknowledged_at:
                ack_dt = datetime.fromisoformat(inc.acknowledged_at.replace("Z", "+00:00"))
                ack_durations.append((ack_dt - start_dt).total_seconds())

            if inc.resolved_at:
                res_dt = datetime.fromisoformat(inc.resolved_at.replace("Z", "+00:00"))
                resolve_durations.append((res_dt - start_dt).total_seconds())

            # Check assignment timeline
            for tle in inc.timeline:
                if tle.get("action") == "incident.assigned":
                    tle_dt = datetime.fromisoformat(tle["timestamp"].replace("Z", "+00:00"))
                    assign_durations.append((tle_dt - start_dt).total_seconds())
                    break

            if inc.resolution_category == ResolutionCategory.FALSE_ALARM.value:
                false_alarms += 1

        avg_ack = sum(ack_durations) / len(ack_durations) if ack_durations else None
        avg_assign = sum(assign_durations) / len(assign_durations) if assign_durations else None
        avg_res = sum(resolve_durations) / len(resolve_durations) if resolve_durations else None
        fa_rate = (false_alarms / total) if total > 0 else 0.0

        # Notifications count
        notif_cursor = db.notifications.find({})
        notif_stats = {}
        async for ndoc in notif_cursor:
            st = ndoc.get("status", "UNKNOWN")
            notif_stats[st] = notif_stats.get(st, 0) + 1

        return IncidentMetricsResponse(
            total_incidents=total,
            open_incidents=open_cnt,
            acknowledged_incidents=ack_cnt,
            responding_incidents=resp_cnt,
            escalated_incidents=esc_cnt,
            resolved_incidents=res_cnt,
            closed_incidents=closed_cnt,
            cancelled_incidents=cancel_cnt,
            avg_time_to_acknowledge_seconds=avg_ack,
            avg_time_to_assign_seconds=avg_assign,
            avg_time_to_resolve_seconds=avg_res,
            escalation_count=esc_cnt,
            false_alarm_rate=fa_rate,
            notification_stats=notif_stats,
        )


incident_service = IncidentCommandService()
