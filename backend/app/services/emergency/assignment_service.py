"""
TourSafe Incident Assignment Service

Orchestrates the complete responder assignment lifecycle:
AUTHORITY ASSIGNMENT -> RESPONDER ACCEPTANCE/REJECTION -> RESPONSE COMMENCEMENT
-> ARRIVAL WITH PROXIMITY VALIDATION -> ON-SCENE OPERATIONS -> RESPONSE COMPLETION.

Enforces strict state transitions, atomic concurrency locking, and immutable incident timeline integration.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from ...core import database as db_core
from ...schemas.emergency import (
    AssignmentArrivedRequest,
    AssignmentCompleteRequest,
    AssignmentHandoverRequest,
    AssignmentRecord,
    AssignmentRejectRequest,
    AssignmentStatus,
    FieldNotesBatchSyncRequest,
    FieldNotesBatchSyncResponse,
    HandoverReason,
    IncidentNoteRecord,
    IncidentStatus,
    NotificationChannel,
    RejectionReason,
    ResponderRecord,
    ResponderStatus,
    SceneAssessmentRequest,
    TimelineEventRecord,
)
from ...schemas.realtime import RealtimeEventEnvelope, RealtimeEventType
from ...services.realtime_bus import realtime_bus
from .notifications import notification_service
from .responder_service import haversine_distance_meters, responder_service


def get_database():
    return db_core.get_database()


logger = logging.getLogger("toursafe.emergency.assignment")

# Proximity radius threshold for physical arrival verification (meters)
ARRIVAL_PROXIMITY_RADIUS_METERS = 500.0


class AssignmentService:
    """
    Service managing incident assignment records and operational coordination.
    """

    async def get_assignment(self, assignment_id: str) -> Optional[AssignmentRecord]:
        db = get_database()
        doc = await db.incident_assignments.find_one({"assignment_id": assignment_id})
        if not doc:
            return None
        return AssignmentRecord(**doc)

    async def get_active_assignment_for_responder(self, responder_id: str) -> Optional[AssignmentRecord]:
        db = get_database()
        doc = await db.incident_assignments.find_one({
            "responder_id": responder_id,
            "status": {"$in": [AssignmentStatus.PENDING.value, AssignmentStatus.ACCEPTED.value, AssignmentStatus.ACTIVE.value]},
        })
        if not doc:
            return None
        return AssignmentRecord(**doc)

    async def list_assignments_for_incident(self, incident_id: str) -> List[AssignmentRecord]:
        db = get_database()
        cursor = db.incident_assignments.find({"incident_id": incident_id}).sort("created_at", -1)
        items = []
        async for doc in cursor:
            items.append(AssignmentRecord(**doc))
        return items

    async def create_assignment(
        self,
        incident_id: str,
        responder_id: str,
        assigned_by: str,
        unit_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> AssignmentRecord:
        """
        Creates an assignment record, locks the responder atomically, and updates incident state.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Fetch incident
        incident_doc = await db.incidents.find_one({"incident_id": incident_id})
        if not incident_doc:
            raise ValueError(f"Incident '{incident_id}' not found")

        # 2. Fetch responder and verify capability & status
        responder = await responder_service.get_responder(responder_id)
        if not responder or not responder.active:
            raise ValueError(f"Responder '{responder_id}' is not active or not found")

        if responder.status not in (ResponderStatus.AVAILABLE, ResponderStatus.UNAVAILABLE):
            raise ValueError(f"Responder '{responder.name}' is currently in status '{responder.status.value}' and cannot receive new assignments")

        # 3. Create assignment record
        assignment_id = f"asgn_{uuid.uuid4().hex[:12]}"
        assignment = AssignmentRecord(
            assignment_id=assignment_id,
            incident_id=incident_id,
            responder_id=responder_id,
            unit_id=unit_id or responder.unit_id,
            assigned_by=assigned_by,
            assigned_at=now_iso,
            status=AssignmentStatus.PENDING,
            notes=notes,
            created_at=now_iso,
            updated_at=now_iso,
        )

        # 4. Atomic lock on responder
        locked_responder = await responder_service.assign_to_incident(
            responder_id=responder_id,
            incident_id=incident_id,
            assignment_id=assignment_id,
        )
        if not locked_responder:
            raise ValueError(f"Responder '{responder.name}' could not be locked. Possible concurrent assignment conflict.")

        # 5. Persist assignment
        await db.incident_assignments.insert_one(assignment.model_dump())

        # 6. Update Incident record
        prev_incident_status = incident_doc.get("status", "OPEN")
        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type="AUTHORITY",
            actor_id=assigned_by,
            action="incident.assigned",
            previous_state=prev_incident_status,
            new_state=IncidentStatus.ASSIGNED.value,
            metadata={
                "assignment_id": assignment_id,
                "responder_id": responder_id,
                "responder_name": responder.name,
                "responder_type": responder.type.value if hasattr(responder.type, "value") else str(responder.type),
                "unit_id": assignment.unit_id,
            },
            reason=notes or f"Assigned to responder {responder.name}",
        )

        await db.incidents.update_one(
            {"incident_id": incident_id},
            {
                "$set": {
                    "status": IncidentStatus.ASSIGNED.value,
                    "assigned_to": responder_id,
                    "assigned_unit": assignment.unit_id,
                    "responder_type": responder.type.value if hasattr(responder.type, "value") else str(responder.type),
                    "updated_at": now_iso,
                },
                "$inc": {"version": 1},
                "$push": {"timeline": tle.model_dump()},
            },
        )

        # 7. Broadcast realtime event
        await realtime_bus.publish_event(
            event_type=RealtimeEventType.RESPONDER_ASSIGNED.value,
            payload={
                "assignment_id": assignment_id,
                "incident_id": incident_id,
                "responder_id": responder_id,
                "assigned_by": assigned_by,
                "unit_id": assignment.unit_id,
                "timestamp": now_iso,
            },
            target_role="authority",
        )

        # 8. Notify responder through channel
        await notification_service.send_notification(
            recipient=responder.contact_channel or responder_id,
            channel=NotificationChannel.PUSH,
            subject="TourSafe Incident Assignment",
            message=f"You have been assigned to Incident {incident_id}.",
            incident_id=incident_id,
            recipient_type="RESPONDER",
            metadata={"assignment_id": assignment_id},
        )

        return assignment

    async def accept_assignment(
        self,
        incident_id: str,
        assignment_id: str,
        responder_id: str,
        notes: Optional[str] = None,
    ) -> AssignmentRecord:
        """
        Responder accepts pending assignment.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        assignment = await self.get_assignment(assignment_id)
        if not assignment:
            raise ValueError(f"Assignment '{assignment_id}' not found")
        if assignment.responder_id != responder_id:
            raise ValueError("Unauthorized: You are not the assigned responder for this incident")
        if assignment.status != AssignmentStatus.PENDING:
            raise ValueError(f"Cannot accept assignment in status '{assignment.status.value}'")

        # Update assignment to ACCEPTED
        assignment.status = AssignmentStatus.ACCEPTED
        assignment.accepted_at = now_iso
        assignment.updated_at = now_iso
        if notes:
            assignment.notes = f"{assignment.notes or ''}\n[Accept]: {notes}".strip()

        await db.incident_assignments.replace_one({"assignment_id": assignment_id}, assignment.model_dump())

        # Timeline event
        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type="RESPONDER",
            actor_id=responder_id,
            action="responder.accepted",
            previous_state=AssignmentStatus.PENDING.value,
            new_state=AssignmentStatus.ACCEPTED.value,
            metadata={"assignment_id": assignment_id},
            reason=notes or "Responder accepted assignment",
        )
        await db.incidents.update_one(
            {"incident_id": incident_id},
            {
                "$set": {"updated_at": now_iso},
                "$inc": {"version": 1},
                "$push": {"timeline": tle.model_dump()},
            },
        )

        # Broadcast realtime event
        await realtime_bus.publish_event(
            event_type=RealtimeEventType.RESPONDER_ACCEPTED.value,
            payload={
                "assignment_id": assignment_id,
                "incident_id": incident_id,
                "responder_id": responder_id,
                "timestamp": now_iso,
            },
            target_role="authority",
        )
        return assignment

    async def reject_assignment(
        self,
        incident_id: str,
        assignment_id: str,
        responder_id: str,
        reason: RejectionReason,
        details: Optional[str] = None,
    ) -> AssignmentRecord:
        """
        Responder rejects pending assignment with required reason, releasing responder back to AVAILABLE.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        assignment = await self.get_assignment(assignment_id)
        if not assignment:
            raise ValueError(f"Assignment '{assignment_id}' not found")
        if assignment.responder_id != responder_id:
            raise ValueError("Unauthorized: You are not the assigned responder for this incident")
        if assignment.status != AssignmentStatus.PENDING:
            raise ValueError(f"Cannot reject assignment in status '{assignment.status.value}'")

        # Update assignment to REJECTED
        assignment.status = AssignmentStatus.REJECTED
        assignment.rejected_at = now_iso
        assignment.rejection_reason = f"{reason.value}: {details}" if details else reason.value
        assignment.updated_at = now_iso

        await db.incident_assignments.replace_one({"assignment_id": assignment_id}, assignment.model_dump())

        # Release responder
        await responder_service.release_from_incident(responder_id)

        # Timeline event
        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type="RESPONDER",
            actor_id=responder_id,
            action="responder.rejected",
            previous_state=AssignmentStatus.PENDING.value,
            new_state=AssignmentStatus.REJECTED.value,
            metadata={"assignment_id": assignment_id, "rejection_reason": assignment.rejection_reason},
            reason=assignment.rejection_reason,
        )
        await db.incidents.update_one(
            {"incident_id": incident_id},
            {
                "$set": {
                    "status": IncidentStatus.ASSESSING.value,
                    "assigned_to": None,
                    "updated_at": now_iso,
                },
                "$inc": {"version": 1},
                "$push": {"timeline": tle.model_dump()},
            },
        )

        # Broadcast realtime event
        await realtime_bus.publish_event(
            event_type=RealtimeEventType.RESPONDER_REJECTED.value,
            payload={
                "assignment_id": assignment_id,
                "incident_id": incident_id,
                "responder_id": responder_id,
                "reason": assignment.rejection_reason,
                "timestamp": now_iso,
            },
            target_role="authority",
        )
        return assignment

    async def start_response(
        self,
        incident_id: str,
        assignment_id: str,
        responder_id: str,
        notes: Optional[str] = None,
    ) -> AssignmentRecord:
        """
        Responder begins transit / active response.
        Transitions assignment -> ACTIVE, responder -> RESPONDING, incident -> RESPONDING.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        assignment = await self.get_assignment(assignment_id)
        if not assignment:
            raise ValueError(f"Assignment '{assignment_id}' not found")
        if assignment.responder_id != responder_id:
            raise ValueError("Unauthorized: You are not the assigned responder for this incident")
        if assignment.status not in (AssignmentStatus.PENDING, AssignmentStatus.ACCEPTED):
            raise ValueError(f"Cannot start response for assignment in status '{assignment.status.value}'")

        # Update assignment
        assignment.status = AssignmentStatus.ACTIVE
        assignment.started_at = now_iso
        assignment.updated_at = now_iso
        if notes:
            assignment.notes = f"{assignment.notes or ''}\n[Start]: {notes}".strip()

        await db.incident_assignments.replace_one({"assignment_id": assignment_id}, assignment.model_dump())

        # Update responder status to RESPONDING
        await responder_service.set_responder_status(responder_id, ResponderStatus.RESPONDING, reason="Response started")

        # Update incident status to RESPONDING
        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type="RESPONDER",
            actor_id=responder_id,
            action="incident.response.started",
            previous_state=IncidentStatus.ASSIGNED.value,
            new_state=IncidentStatus.RESPONDING.value,
            metadata={"assignment_id": assignment_id},
            reason=notes or "Responder en route",
        )
        await db.incidents.update_one(
            {"incident_id": incident_id},
            {
                "$set": {
                    "status": IncidentStatus.RESPONDING.value,
                    "updated_at": now_iso,
                },
                "$inc": {"version": 1},
                "$push": {"timeline": tle.model_dump()},
            },
        )

        # Broadcast realtime event
        await realtime_bus.publish_event(
            event_type=RealtimeEventType.RESPONDER_RESPONSE_STARTED.value,
            payload={
                "assignment_id": assignment_id,
                "incident_id": incident_id,
                "responder_id": responder_id,
                "timestamp": now_iso,
            },
            target_role="authority",
        )
        return assignment

    async def mark_arrived(
        self,
        incident_id: str,
        assignment_id: str,
        responder_id: str,
        req: AssignmentArrivedRequest,
    ) -> AssignmentRecord:
        """
        Responder arrives on scene. Validates proximity to incident coordinates if available,
        or accepts controlled override fallback.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        assignment = await self.get_assignment(assignment_id)
        if not assignment:
            raise ValueError(f"Assignment '{assignment_id}' not found")
        if assignment.responder_id != responder_id:
            raise ValueError("Unauthorized: You are not the assigned responder for this incident")
        if assignment.status != AssignmentStatus.ACTIVE:
            raise ValueError(f"Cannot mark arrived on assignment with status '{assignment.status.value}' (must be ACTIVE)")

        # Verify Proximity if coordinates available
        incident_doc = await db.incidents.find_one({"incident_id": incident_id})
        proximity_verified = False
        distance_calculated: Optional[float] = None

        if req.latitude is not None and req.longitude is not None and incident_doc and incident_doc.get("location_data"):
            inc_loc = incident_doc["location_data"]
            if "latitude" in inc_loc and "longitude" in inc_loc:
                distance_calculated = haversine_distance_meters(
                    req.latitude, req.longitude,
                    float(inc_loc["latitude"]), float(inc_loc["longitude"])
                )
                if distance_calculated <= ARRIVAL_PROXIMITY_RADIUS_METERS:
                    proximity_verified = True

        if not proximity_verified and not req.force_override and distance_calculated is not None:
            if distance_calculated > ARRIVAL_PROXIMITY_RADIUS_METERS:
                raise ValueError(
                    f"Arrival proximity check failed: Responder is {int(distance_calculated)}m away from incident "
                    f"(limit is {int(ARRIVAL_PROXIMITY_RADIUS_METERS)}m). Enable force_override if GPS is degraded."
                )

        arrival_loc = None
        if req.latitude is not None and req.longitude is not None:
            arrival_loc = {
                "latitude": req.latitude,
                "longitude": req.longitude,
                "accuracy": req.accuracy,
                "proximity_verified": proximity_verified,
                "distance_to_incident_meters": distance_calculated,
            }

        # Update assignment
        assignment.arrived_at = now_iso
        assignment.arrival_location = arrival_loc
        assignment.arrival_accuracy = req.accuracy
        assignment.updated_at = now_iso
        if req.notes:
            assignment.notes = f"{assignment.notes or ''}\n[Arrived]: {req.notes}".strip()

        await db.incident_assignments.replace_one({"assignment_id": assignment_id}, assignment.model_dump())

        # Update responder status to ON_SCENE
        await responder_service.set_responder_status(responder_id, ResponderStatus.ON_SCENE, reason="Responder arrived on scene")

        # Timeline event
        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type="RESPONDER",
            actor_id=responder_id,
            action="responder.arrived",
            previous_state=ResponderStatus.RESPONDING.value,
            new_state=ResponderStatus.ON_SCENE.value,
            metadata={
                "assignment_id": assignment_id,
                "arrival_location": arrival_loc,
                "proximity_verified": proximity_verified,
            },
            reason=req.notes or "Responder marked arrived on scene",
        )
        await db.incidents.update_one(
            {"incident_id": incident_id},
            {
                "$set": {"updated_at": now_iso},
                "$inc": {"version": 1},
                "$push": {"timeline": tle.model_dump()},
            },
        )

        # Broadcast realtime event
        await realtime_bus.publish_event(
            event_type=RealtimeEventType.RESPONDER_ARRIVED.value,
            payload={
                "assignment_id": assignment_id,
                "incident_id": incident_id,
                "responder_id": responder_id,
                "arrival_location": arrival_loc,
                "timestamp": now_iso,
            },
            target_role="authority",
        )
        return assignment

    async def complete_response(
        self,
        incident_id: str,
        assignment_id: str,
        responder_id: str,
        req: AssignmentCompleteRequest,
    ) -> AssignmentRecord:
        """
        Responder concludes response actions with mandatory completion reason.
        Releases responder back to AVAILABLE.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        assignment = await self.get_assignment(assignment_id)
        if not assignment:
            raise ValueError(f"Assignment '{assignment_id}' not found")
        if assignment.responder_id != responder_id:
            raise ValueError("Unauthorized: You are not the assigned responder for this incident")
        if assignment.status != AssignmentStatus.ACTIVE:
            raise ValueError(f"Cannot complete assignment in status '{assignment.status.value}'")

        # Update assignment to COMPLETED
        assignment.status = AssignmentStatus.COMPLETED
        assignment.completed_at = now_iso
        assignment.completion_reason = req.completion_reason
        assignment.completion_notes = req.resolution_notes
        assignment.updated_at = now_iso

        await db.incident_assignments.replace_one({"assignment_id": assignment_id}, assignment.model_dump())

        # Release responder back to AVAILABLE
        await responder_service.release_from_incident(responder_id)

        # Timeline event & Note
        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type="RESPONDER",
            actor_id=responder_id,
            action="responder.completed",
            previous_state=AssignmentStatus.ACTIVE.value,
            new_state=AssignmentStatus.COMPLETED.value,
            metadata={
                "assignment_id": assignment_id,
                "completion_reason": req.completion_reason,
            },
            reason=req.completion_reason,
        )

        note_rec = IncidentNoteRecord(
            incident_id=incident_id,
            author_id=responder_id,
            author_role="responder",
            timestamp=now_iso,
            content=f"[Response Complete]: {req.completion_reason}. Details: {req.resolution_notes or 'None'}",
        )

        await db.incidents.update_one(
            {"incident_id": incident_id},
            {
                "$set": {"updated_at": now_iso},
                "$inc": {"version": 1},
                "$push": {
                    "timeline": tle.model_dump(),
                    "notes_list": note_rec.model_dump(),
                },
            },
        )

        # Broadcast realtime event
        await realtime_bus.publish_event(
            event_type=RealtimeEventType.RESPONDER_COMPLETED.value,
            payload={
                "assignment_id": assignment_id,
                "incident_id": incident_id,
                "responder_id": responder_id,
                "completion_reason": req.completion_reason,
                "timestamp": now_iso,
            },
            target_role="authority",
        )
        return assignment

    async def request_handover(
        self,
        incident_id: str,
        assignment_id: str,
        responder_id: str,
        req: AssignmentHandoverRequest,
    ) -> AssignmentRecord:
        """
        Responder requests operational handover due to medical, capability, terrain, or shift constraints.
        Releases current responder, marks assignment CANCELLED or HANDOVER, and prompts authority reassignment.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        assignment = await self.get_assignment(assignment_id)
        if not assignment:
            raise ValueError(f"Assignment '{assignment_id}' not found")
        if assignment.responder_id != responder_id:
            raise ValueError("Unauthorized: You are not the assigned responder for this incident")
        status_val = assignment.status.value if hasattr(assignment.status, "value") else str(assignment.status)
        if status_val not in ("ACCEPTED", "ACTIVE", "PENDING"):
            raise ValueError(f"Cannot request handover for assignment in status '{status_val}'")

        # Update assignment to CANCELLED with handover reason
        assignment.status = AssignmentStatus.CANCELLED
        assignment.cancelled_at = now_iso
        assignment.cancellation_reason = f"HANDOVER_REQUESTED: {req.reason.value} - {req.details or 'No additional details'}"
        assignment.updated_at = now_iso

        await db.incident_assignments.replace_one({"assignment_id": assignment_id}, assignment.model_dump())

        # Release responder back to AVAILABLE
        await responder_service.release_from_incident(responder_id)

        # Timeline event & Note
        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type="RESPONDER",
            actor_id=responder_id,
            action="responder.handover_requested",
            previous_state=status_val,
            new_state=AssignmentStatus.CANCELLED.value,
            metadata={
                "assignment_id": assignment_id,
                "handover_reason": req.reason.value,
                "details": req.details,
                "replacement_capability": req.replacement_capability,
            },
            reason=f"Handover requested: {req.reason.value}",
        )

        note_rec = IncidentNoteRecord(
            incident_id=incident_id,
            author_id=responder_id,
            author_role="responder",
            timestamp=now_iso,
            content=f"[Handover Requested]: {req.reason.value}. {req.details or ''}. Requested Capability: {req.replacement_capability or 'Standard'}",
        )

        # Update incident status back to OPEN / ACKNOWLEDGED for dispatch reassignment
        await db.incidents.update_one(
            {"incident_id": incident_id},
            {
                "$set": {
                    "status": IncidentStatus.ACKNOWLEDGED.value,
                    "assigned_to": None,
                    "updated_at": now_iso,
                },
                "$inc": {"version": 1},
                "$push": {
                    "timeline": tle.model_dump(),
                    "notes_list": note_rec.model_dump(),
                },
            },
        )

        # Broadcast realtime event to authority command
        await realtime_bus.publish_event(
            event_type="incident.handover_requested",
            payload={
                "assignment_id": assignment_id,
                "incident_id": incident_id,
                "responder_id": responder_id,
                "reason": req.reason.value,
                "details": req.details,
                "replacement_capability": req.replacement_capability,
                "timestamp": now_iso,
            },
            target_role="authority",
        )
        return assignment

    async def submit_scene_assessment(
        self,
        incident_id: str,
        assignment_id: str,
        responder_id: str,
        req: SceneAssessmentRequest,
    ) -> Dict[str, Any]:
        """
        Submits structured field scene assessment from responder on scene.
        Updates incident timeline and notes with auditable assessment categorization.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        assignment = await self.get_assignment(assignment_id)
        if not assignment:
            raise ValueError(f"Assignment '{assignment_id}' not found")
        if assignment.responder_id != responder_id:
            raise ValueError("Unauthorized: You are not the assigned responder for this incident")

        status_val = assignment.status.value if hasattr(assignment.status, "value") else str(assignment.status)

        tle = TimelineEventRecord(
            incident_id=incident_id,
            timestamp=now_iso,
            actor_type="RESPONDER",
            actor_id=responder_id,
            action="responder.scene_assessment",
            previous_state=status_val,
            new_state=status_val,
            metadata={
                "assignment_id": assignment_id,
                "assessment_category": req.category.value,
                "tourist_status_observed": req.tourist_status_observed,
                "follow_up_required": req.follow_up_required,
                "evidence_metadata": req.evidence_metadata,
            },
            reason=f"Scene assessment: {req.category.value}",
        )

        note_rec = IncidentNoteRecord(
            incident_id=incident_id,
            author_id=responder_id,
            author_role="responder",
            timestamp=now_iso,
            content=f"[Scene Assessment - {req.category.value}]: {req.notes or 'No commentary'}. Observed: {req.tourist_status_observed or 'N/A'}. Follow-up: {req.follow_up_required}",
        )

        await db.incidents.update_one(
            {"incident_id": incident_id},
            {
                "$set": {
                    "updated_at": now_iso,
                    "last_scene_assessment": {
                        "category": req.category.value,
                        "timestamp": now_iso,
                        "assessed_by": responder_id,
                        "follow_up_required": req.follow_up_required,
                    },
                },
                "$inc": {"version": 1},
                "$push": {
                    "timeline": tle.model_dump(),
                    "notes_list": note_rec.model_dump(),
                },
            },
        )

        await realtime_bus.publish_event(
            event_type="incident.scene_assessed",
            payload={
                "incident_id": incident_id,
                "assignment_id": assignment_id,
                "responder_id": responder_id,
                "category": req.category.value,
                "timestamp": now_iso,
            },
            target_role="authority",
        )

        return {
            "success": True,
            "incident_id": incident_id,
            "category": req.category.value,
            "timestamp": now_iso,
        }

    async def sync_field_notes(
        self,
        responder_id: str,
        req: FieldNotesBatchSyncRequest,
    ) -> FieldNotesBatchSyncResponse:
        """
        Batch syncs offline field notes with deduplication and timeline integration.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        synced_ids = []
        failed_ids = []

        for item in req.notes:
            try:
                inc_doc = await db.incidents.find_one({"incident_id": item.incident_id})
                if not inc_doc:
                    failed_ids.append(item.client_note_id)
                    continue

                notes_list = inc_doc.get("notes_list", [])
                if any(n.get("client_note_id") == item.client_note_id for n in notes_list if isinstance(n, dict)):
                    synced_ids.append(item.client_note_id)
                    continue

                note_doc = {
                    "note_id": f"fn_{uuid.uuid4().hex[:12]}",
                    "client_note_id": item.client_note_id,
                    "incident_id": item.incident_id,
                    "author_id": responder_id,
                    "author_role": "responder",
                    "timestamp": item.recorded_at or now_iso,
                    "synced_at": now_iso,
                    "content": f"[Offline Note Sync]: {item.content}",
                    "location": {
                        "latitude": item.latitude,
                        "longitude": item.longitude,
                    } if item.latitude and item.longitude else None,
                }

                tle = TimelineEventRecord(
                    incident_id=item.incident_id,
                    timestamp=item.recorded_at or now_iso,
                    actor_type="RESPONDER",
                    actor_id=responder_id,
                    action="responder.field_note_synced",
                    metadata={
                        "client_note_id": item.client_note_id,
                        "synced_at": now_iso,
                    },
                    reason="Offline field note synced",
                )

                await db.incidents.update_one(
                    {"incident_id": item.incident_id},
                    {
                        "$set": {"updated_at": now_iso},
                        "$inc": {"version": 1},
                        "$push": {
                            "timeline": tle.model_dump(),
                            "notes_list": note_doc,
                        },
                    },
                )
                synced_ids.append(item.client_note_id)
            except Exception as ex:
                logger.error("Failed to sync offline note %s: %s", item.client_note_id, ex)
                failed_ids.append(item.client_note_id)

        return FieldNotesBatchSyncResponse(
            synced_count=len(synced_ids),
            synced_ids=synced_ids,
            failed_ids=failed_ids,
            timestamp=now_iso,
        )


    async def list_responder_history(
        self,
        responder_id: str,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Lists paginated historical assignments and completed missions for a responder.
        """
        db = get_database()
        cursor = db.incident_assignments.find(
            {"responder_id": responder_id}
        ).sort("created_at", -1).skip(skip).limit(limit)

        items = []
        async for doc in cursor:
            inc_doc = await db.incidents.find_one({"incident_id": doc.get("incident_id")})
            doc["_id"] = str(doc.get("_id", ""))
            doc["incident_summary"] = {
                "incident_id": inc_doc.get("incident_id") if inc_doc else doc.get("incident_id"),
                "severity": inc_doc.get("severity", "UNKNOWN") if inc_doc else "UNKNOWN",
                "source": inc_doc.get("source", "SAFETY_ENGINE") if inc_doc else "SAFETY_ENGINE",
                "status": inc_doc.get("status", "CLOSED") if inc_doc else "CLOSED",
                "location_data": inc_doc.get("location_data") if inc_doc else None,
                "reasons": inc_doc.get("reasons", []) if inc_doc else [],
            } if inc_doc else None
            items.append(doc)
        return items


assignment_service = AssignmentService()

