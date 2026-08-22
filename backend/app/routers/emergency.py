"""
TourSafe Emergency Response & Incident Command REST API Endpoints

Authority Endpoints:
- GET /api/v1/authority/incidents/metrics
- GET /api/v1/authority/incidents/{incident_id}/timeline
- POST /api/v1/authority/incidents/{incident_id}/assess
- POST /api/v1/authority/incidents/{incident_id}/assign
- POST /api/v1/authority/incidents/{incident_id}/response-start
- POST /api/v1/authority/incidents/{incident_id}/escalate
- POST /api/v1/authority/incidents/{incident_id}/notes
- POST /api/v1/authority/incidents/{incident_id}/cancel
- POST /api/v1/authority/incidents/{incident_id}/close
- GET /api/v1/authority/responders
- POST /api/v1/authority/responders
- GET /api/v1/authority/responders/{responder_id}
- PATCH /api/v1/authority/responders/{responder_id}

Tourist Endpoints:
- POST /api/v1/tourists/me/sos
- POST /api/v1/tourists/me/sos/{sos_id}/cancel
- GET /api/v1/tourists/me/sos/active
- POST /api/v1/sos/trigger (Compatibility)
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..core import database as db_core


def get_database():
    return db_core.get_database()
from ..routers.auth import get_current_user
from ..schemas.emergency import (
    AssignmentAcceptRequest,
    AssignmentArrivedRequest,
    AssignmentCompleteRequest,
    AssignmentRecord,
    AssignmentRejectRequest,
    IncidentAcknowledgeRequest,
    IncidentAssessRequest,
    IncidentAssignRequest,
    IncidentCancelRequest,
    IncidentCloseRequest,
    IncidentEscalateRequest,
    IncidentMetricsResponse,
    IncidentNoteCreateRequest,
    IncidentNoteRecord,
    IncidentResolveRequest,
    IncidentResponseStartRequest,
    OperationalMessageCreateRequest,
    OperationalMessageRecord,
    ResolutionCategory,
    ResponderCreateRequest,
    ResponderRecord,
    ResponderStatus,
    ResponderType,
    ResponderUpdateRequest,
    SOSCancelRequest,
    SOSRequest,
    SOSResponse,
    TimelineEventRecord,
)
from ..schemas.safety import IncidentRecord
from ..services.emergency import (
    assignment_service,
    incident_service,
    messaging_service,
    responder_service,
    sos_service,
)

logger = logging.getLogger("toursafe.emergency.router")

router = APIRouter(tags=["emergency"])


# ---------------------------------------------------------------------------
# Tourist SOS Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/api/v1/tourists/me/sos",
    response_model=SOSResponse,
    summary="Trigger manual emergency SOS from authenticated tourist",
)
async def trigger_manual_sos(
    payload: SOSRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authenticated tourists may initiate manual SOS",
        )

    # Resolve tourist_id from profile or user_id
    tourist_id = user_id
    try:
        db = get_database()
        t_doc = await db.tourists.find_one({"user_id": user_id})
        if t_doc and t_doc.get("id"):
            tourist_id = t_doc["id"]
    except Exception:
        pass

    try:
        response = await sos_service.trigger_sos(tourist_id=tourist_id, req=payload)
        return response
    except Exception as ex:
        logger.error("Failed to trigger SOS for tourist %s: %s", tourist_id, ex)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(ex))


@router.post(
    "/api/v1/sos/trigger",
    response_model=SOSResponse,
    summary="Convenience alias for manual SOS trigger",
)
async def trigger_sos_alias(
    payload: SOSRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    return await trigger_manual_sos(payload, user_id_role)


@router.post(
    "/api/v1/tourists/me/sos/{sos_id}/cancel",
    summary="Cancel active manual SOS with mandatory explanation",
)
async def cancel_manual_sos(
    sos_id: str,
    payload: SOSCancelRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authenticated tourists may cancel their own SOS",
        )

    tourist_id = user_id
    try:
        db = get_database()
        t_doc = await db.tourists.find_one({"user_id": user_id})
        if t_doc and t_doc.get("id"):
            tourist_id = t_doc["id"]
    except Exception:
        pass

    try:
        return await sos_service.cancel_sos(tourist_id=tourist_id, sos_id=sos_id, req=payload)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.get(
    "/api/v1/tourists/me/sos/active",
    summary="Get active SOS record for authenticated tourist",
)
async def get_active_tourist_sos(
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tourist access required",
        )

    tourist_id = user_id
    try:
        db = get_database()
        t_doc = await db.tourists.find_one({"user_id": user_id})
        if t_doc and t_doc.get("id"):
            tourist_id = t_doc["id"]
    except Exception:
        pass

    active = await sos_service.get_active_sos_for_tourist(tourist_id)
    return {"active_sos": active}


# ---------------------------------------------------------------------------
# Authority Incident Command Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/authority/incidents/metrics",
    response_model=IncidentMetricsResponse,
    summary="Get operational command metrics (time-to-acknowledge, time-to-resolve, false alarm rate)",
)
async def get_command_metrics(
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    return await incident_service.get_metrics()


@router.get(
    "/api/v1/authority/incidents/{incident_id}/timeline",
    response_model=List[TimelineEventRecord],
    summary="Get immutable chronological audit timeline for an incident",
)
async def get_incident_timeline(
    incident_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    incident = await incident_service.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found")

    return [TimelineEventRecord(**t) for t in incident.timeline]


@router.post(
    "/api/v1/authority/incidents/{incident_id}/acknowledge",
    response_model=IncidentRecord,
    summary="Acknowledge incident by authority and transition from OPEN to ACKNOWLEDGED",
)
async def acknowledge_incident(
    incident_id: str,
    payload: IncidentAcknowledgeRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    try:
        return await incident_service.acknowledge_incident(
            incident_id=incident_id,
            authority_id=user_id,
            notes=payload.notes,
            expected_version=payload.version,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post(
    "/api/v1/authority/incidents/{incident_id}/assess",
    response_model=IncidentRecord,
    summary="Move incident to ASSESSING state with optional severity update",
)
async def assess_incident(
    incident_id: str,
    payload: IncidentAssessRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    try:
        return await incident_service.assess_incident(
            incident_id=incident_id,
            authority_id=user_id,
            severity=payload.severity,
            notes=payload.notes,
            expected_version=payload.version,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post(
    "/api/v1/authority/incidents/{incident_id}/assign",
    response_model=IncidentRecord,
    summary="Assign responder or unit to incident",
)
async def assign_incident_responder(
    incident_id: str,
    payload: IncidentAssignRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    try:
        return await incident_service.assign_responder(
            incident_id=incident_id,
            authority_id=user_id,
            responder_id=payload.responder_id,
            unit_id=payload.unit_id,
            notes=payload.notes,
            expected_version=payload.version,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post(
    "/api/v1/authority/incidents/{incident_id}/response-start",
    response_model=IncidentRecord,
    summary="Mark responder en route / actively engaging",
)
async def start_incident_response(
    incident_id: str,
    payload: IncidentResponseStartRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    try:
        return await incident_service.start_response(
            incident_id=incident_id,
            actor_id=user_id,
            notes=payload.notes,
            estimated_arrival_minutes=payload.estimated_arrival_minutes,
            expected_version=payload.version,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post(
    "/api/v1/authority/incidents/{incident_id}/escalate",
    response_model=IncidentRecord,
    summary="Manually escalate an active incident",
)
async def escalate_incident(
    incident_id: str,
    payload: IncidentEscalateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    try:
        return await incident_service.manual_escalate(
            incident_id=incident_id,
            authority_id=user_id,
            reason=payload.reason,
            target_severity=payload.target_severity,
            notes=payload.notes,
            expected_version=payload.version,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post(
    "/api/v1/authority/incidents/{incident_id}/notes",
    response_model=IncidentNoteRecord,
    summary="Append an operational note to the incident timeline",
)
async def add_note_to_incident(
    incident_id: str,
    payload: IncidentNoteCreateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    try:
        return await incident_service.add_incident_note(
            incident_id=incident_id,
            author_id=user_id,
            author_role=role,
            content=payload.content,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post(
    "/api/v1/authority/incidents/{incident_id}/resolve",
    response_model=IncidentRecord,
    summary="Resolve an active incident with mandatory reason and category",
)
async def resolve_incident_authority(
    incident_id: str,
    payload: IncidentResolveRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    try:
        return await incident_service.resolve_incident(
            incident_id=incident_id,
            authority_id=user_id,
            resolution_reason=payload.resolution_reason,
            resolution_category=payload.resolution_category,
            notes=payload.notes,
            expected_version=payload.version,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.get(
    "/api/v1/authority/incidents/{incident_id}",
    response_model=IncidentRecord,
    summary="Get incident record details by ID",
)
async def get_incident_details(
    incident_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    inc = await incident_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found")
    return inc


@router.post(
    "/api/v1/authority/incidents/{incident_id}/cancel",
    response_model=IncidentRecord,
    summary="Cancel an incident or mark as false alarm",
)
async def cancel_incident_authority(
    incident_id: str,
    payload: IncidentCancelRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    try:
        return await incident_service.cancel_incident(
            incident_id=incident_id,
            actor_id=user_id,
            actor_type="AUTHORITY",
            cancellation_reason=payload.cancellation_reason,
            is_false_alarm=payload.is_false_alarm,
            notes=payload.notes,
            expected_version=payload.version,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post(
    "/api/v1/authority/incidents/{incident_id}/close",
    response_model=IncidentRecord,
    summary="Formally close and archive a resolved or cancelled incident",
)
async def close_incident_authority(
    incident_id: str,
    payload: IncidentCloseRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority admin access required to close incident")

    try:
        return await incident_service.close_incident(
            incident_id=incident_id,
            authority_id=user_id,
            notes=payload.notes,
            expected_version=payload.version,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


# ---------------------------------------------------------------------------
# Responder Management Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/authority/responders",
    response_model=List[ResponderRecord],
    summary="List registered responder units and operators",
)
async def list_responders(
    status_filter: Optional[ResponderStatus] = Query(None, alias="status"),
    responder_type: Optional[ResponderType] = Query(None, alias="type"),
    active_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    items, _ = await responder_service.list_responders(
        status=status_filter,
        responder_type=responder_type,
        active_only=active_only,
        limit=limit,
        skip=skip,
    )
    return items


@router.post(
    "/api/v1/authority/responders",
    response_model=ResponderRecord,
    summary="Register a new responder unit",
)
async def create_responder(
    payload: ResponderCreateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority admin access required")

    return await responder_service.create_responder(payload)


@router.get(
    "/api/v1/authority/responders/{responder_id}",
    response_model=ResponderRecord,
    summary="Get responder unit details by ID",
)
async def get_responder_by_id(
    responder_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    resp = await responder_service.get_responder(responder_id)
    if not resp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Responder '{responder_id}' not found")
    return resp


@router.patch(
    "/api/v1/authority/responders/{responder_id}",
    response_model=ResponderRecord,
    summary="Update responder unit status, capabilities or location",
)
async def update_responder_status(
    responder_id: str,
    payload: ResponderUpdateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    updated = await responder_service.update_responder(responder_id, payload)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Responder '{responder_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# Incident Assignment & Operations Workflow Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/api/v1/authority/incidents/{incident_id}/assignments",
    response_model=AssignmentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create responder assignment for incident with optimistic concurrency lock",
)
async def create_incident_assignment(
    incident_id: str,
    payload: IncidentAssignRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    try:
        return await assignment_service.create_assignment(
            incident_id=incident_id,
            responder_id=payload.responder_id,
            assigned_by=user_id,
            unit_id=payload.unit_id,
            notes=payload.notes,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.get(
    "/api/v1/authority/incidents/{incident_id}/assignments",
    response_model=List[AssignmentRecord],
    summary="List all assignments for an incident",
)
async def list_incident_assignments(
    incident_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority or responder access required")

    return await assignment_service.list_assignments_for_incident(incident_id)


@router.post(
    "/api/v1/authority/incidents/{incident_id}/assignments/{assignment_id}/accept",
    response_model=AssignmentRecord,
    summary="Responder accepts pending incident assignment",
)
async def accept_assignment(
    incident_id: str,
    assignment_id: str,
    payload: AssignmentAcceptRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("responder", "authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Responder access required")

    # Resolve responder ID
    resp = await responder_service.get_responder_by_user_id(user_id)
    responder_id = resp.responder_id if resp else user_id

    try:
        return await assignment_service.accept_assignment(
            incident_id=incident_id,
            assignment_id=assignment_id,
            responder_id=responder_id,
            notes=payload.notes,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post(
    "/api/v1/authority/incidents/{incident_id}/assignments/{assignment_id}/reject",
    response_model=AssignmentRecord,
    summary="Responder rejects pending incident assignment with mandatory reason",
)
async def reject_assignment(
    incident_id: str,
    assignment_id: str,
    payload: AssignmentRejectRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("responder", "authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Responder access required")

    resp = await responder_service.get_responder_by_user_id(user_id)
    responder_id = resp.responder_id if resp else user_id

    try:
        return await assignment_service.reject_assignment(
            incident_id=incident_id,
            assignment_id=assignment_id,
            responder_id=responder_id,
            reason=payload.reason,
            details=payload.details,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post(
    "/api/v1/authority/incidents/{incident_id}/assignments/{assignment_id}/start",
    response_model=AssignmentRecord,
    summary="Responder starts travel / active response",
)
async def start_assignment_response(
    incident_id: str,
    assignment_id: str,
    payload: IncidentResponseStartRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("responder", "authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Responder access required")

    resp = await responder_service.get_responder_by_user_id(user_id)
    responder_id = resp.responder_id if resp else user_id

    try:
        return await assignment_service.start_response(
            incident_id=incident_id,
            assignment_id=assignment_id,
            responder_id=responder_id,
            notes=payload.notes,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post(
    "/api/v1/authority/incidents/{incident_id}/assignments/{assignment_id}/arrived",
    response_model=AssignmentRecord,
    summary="Responder marks arrived on scene with proximity validation",
)
async def arrive_assignment(
    incident_id: str,
    assignment_id: str,
    payload: AssignmentArrivedRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("responder", "authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Responder access required")

    resp = await responder_service.get_responder_by_user_id(user_id)
    responder_id = resp.responder_id if resp else user_id

    try:
        return await assignment_service.mark_arrived(
            incident_id=incident_id,
            assignment_id=assignment_id,
            responder_id=responder_id,
            req=payload,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post(
    "/api/v1/authority/incidents/{incident_id}/assignments/{assignment_id}/complete",
    response_model=AssignmentRecord,
    summary="Responder completes response operations with resolution note",
)
async def complete_assignment(
    incident_id: str,
    assignment_id: str,
    payload: AssignmentCompleteRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("responder", "authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Responder access required")

    resp = await responder_service.get_responder_by_user_id(user_id)
    responder_id = resp.responder_id if resp else user_id

    try:
        return await assignment_service.complete_response(
            incident_id=incident_id,
            assignment_id=assignment_id,
            responder_id=responder_id,
            req=payload,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


# ---------------------------------------------------------------------------
# Incident Operational Messaging Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/api/v1/authority/incidents/{incident_id}/messages",
    response_model=OperationalMessageRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Send operational incident chat message",
)
async def send_incident_message(
    incident_id: str,
    payload: OperationalMessageCreateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access required")

    sender_type = "RESPONDER" if role == "responder" else "AUTHORITY"
    sender_name = None
    try:
        db = get_database()
        u = await db.users.find_one({"id": user_id})
        if u:
            sender_name = u.get("full_name")
    except Exception:
        pass

    try:
        return await messaging_service.send_message(
            incident_id=incident_id,
            sender_id=user_id,
            sender_type=sender_type,
            sender_name=sender_name,
            req=payload,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.get(
    "/api/v1/authority/incidents/{incident_id}/messages",
    response_model=List[OperationalMessageRecord],
    summary="Get operational messages for an incident",
)
async def get_incident_messages(
    incident_id: str,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access required")

    return await messaging_service.get_messages(
        incident_id=incident_id,
        limit=limit,
        skip=skip,
    )

