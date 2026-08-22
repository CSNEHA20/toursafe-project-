"""
TourSafe Incident Communication & Multi-Party Coordination REST API Router

Provides full operational communication endpoints for live incidents:
- Channel Snapshots & Monotonic Sequence Numbering
- Attributed Multi-Party Messaging (Tourist <-> Authority <-> Responder)
- Message Idempotency via client_message_id
- Explicit Critical Message Acknowledgements
- Delivery and Read Tracking
- Sequence Gap Recovery & Reconnect Reconciliation
- Participant Membership & Presence Tracking
- Incident-Scoped Message Search & Attachment Management
- Multi-Responder Assignment Coordination
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..core import database as db_core
from ..routers.auth import get_current_user
from ..schemas.emergency import (
    AttachmentMetadataRecord,
    AttachmentUploadRequest,
    AttachmentUploadResponse,
    ChannelParticipantAddRequest,
    ChannelParticipantRecord,
    ChannelParticipantUpdateRequest,
    ChannelSnapshotResponse,
    IncidentChannelRecord,
    IncidentMessageRecord,
    MessageAckRequest,
    MessageGapRecoveryResponse,
    MessageSearchResponse,
    MessageSendRequest,
    MultiResponderAssignRequest,
    ParticipantPresenceStatus,
    ParticipantRole,
    ParticipantStatus,
    ResponderAssignmentRole,
)
from ..services.emergency import (
    assignment_service,
    incident_channel_service,
    messaging_service,
    responder_service,
)

logger = logging.getLogger("toursafe.emergency.communication_router")

router = APIRouter(prefix="/api/v1/incidents", tags=["incident-communication"])


def get_database():
    return db_core.get_database()


async def enforce_incident_access(incident_id: str, user_id: str, role: str) -> None:
    """
    Strictly verifies that the caller has authorization to view or interact with this incident.
    Prevents cross-incident and cross-user data leakage.
    """
    can_access = await incident_channel_service.can_user_access_channel(
        incident_id=incident_id,
        user_id=user_id,
        role=role,
    )
    if not can_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You do not have permission to access communication for incident '{incident_id}'",
        )


# ---------------------------------------------------------------------------
# Channel & Snapshot Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/{incident_id}/channel",
    response_model=ChannelSnapshotResponse,
    summary="Get authoritative incident channel snapshot, participants, sequence, unread counts, and recent messages",
)
async def get_incident_channel_snapshot(
    incident_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    await enforce_incident_access(incident_id, user_id, role)

    try:
        snapshot = await messaging_service.get_channel_snapshot(incident_id=incident_id, user_id=user_id)
        return snapshot
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Snapshot error: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load channel snapshot")


# ---------------------------------------------------------------------------
# Message Sending & Querying
# ---------------------------------------------------------------------------

@router.get(
    "/{incident_id}/messages",
    response_model=List[IncidentMessageRecord],
    summary="Retrieve incident messages with monotonic server sequence ordering and pagination",
)
async def get_incident_messages(
    incident_id: str,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    since_sequence: Optional[int] = Query(None, ge=0),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    await enforce_incident_access(incident_id, user_id, role)

    return await messaging_service.get_messages(
        incident_id=incident_id,
        limit=limit,
        skip=skip,
        since_sequence=since_sequence,
    )


@router.post(
    "/{incident_id}/messages",
    response_model=IncidentMessageRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Send an attributed message to the incident channel (idempotent with client_message_id)",
)
async def send_incident_message(
    incident_id: str,
    payload: MessageSendRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    await enforce_incident_access(incident_id, user_id, role)

    # Determine sender role
    if role in ("authority", "admin"):
        sender_role = ParticipantRole.AUTHORITY
    elif role == "responder":
        sender_role = ParticipantRole.RESPONDER
    else:
        sender_role = ParticipantRole.TOURIST

    # Fetch user display name
    db = get_database()
    sender_name = "Participant"
    if role == "tourist":
        t_doc = await db.tourist_profiles.find_one({"user_id": user_id})
        if t_doc:
            sender_name = t_doc.get("full_name", "Tourist")
    elif role == "responder":
        r_doc = await db.responders.find_one({"user_id": user_id})
        if r_doc:
            sender_name = r_doc.get("name", "Responder")
    elif role in ("authority", "admin"):
        a_doc = await db.authority_profiles.find_one({"user_id": user_id})
        if a_doc:
            sender_name = a_doc.get("full_name", "Authority Operator")

    try:
        message = await messaging_service.send_message(
            incident_id=incident_id,
            sender_id=user_id,
            sender_role=sender_role,
            sender_name=sender_name,
            req=payload,
        )
        return message
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as err:
        logger.error("Send message error: %s", err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to post message")


@router.post(
    "/{incident_id}/messages/{message_id}/read",
    summary="Mark incident messages as read up to a specified sequence",
)
async def mark_incident_messages_read(
    incident_id: str,
    message_id: str,
    up_to_sequence: Optional[int] = Query(None, ge=0),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    await enforce_incident_access(incident_id, user_id, role)

    modified = await messaging_service.mark_messages_read(
        incident_id=incident_id,
        reader_id=user_id,
        up_to_sequence=up_to_sequence,
    )
    return {"status": "success", "modified_count": modified, "reader_id": user_id}


@router.post(
    "/{incident_id}/messages/{message_id}/acknowledge",
    response_model=IncidentMessageRecord,
    summary="Explicitly acknowledge a critical operational message",
)
async def acknowledge_incident_message(
    incident_id: str,
    message_id: str,
    payload: MessageAckRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    await enforce_incident_access(incident_id, user_id, role)

    db = get_database()
    actor_name = "Participant"
    if role == "responder":
        r_doc = await db.responders.find_one({"user_id": user_id})
        if r_doc:
            actor_name = r_doc.get("name", "Responder")
    elif role in ("authority", "admin"):
        a_doc = await db.authority_profiles.find_one({"user_id": user_id})
        if a_doc:
            actor_name = a_doc.get("full_name", "Authority Operator")
    elif role == "tourist":
        t_doc = await db.tourist_profiles.find_one({"user_id": user_id})
        if t_doc:
            actor_name = t_doc.get("full_name", "Tourist")

    try:
        ack_msg = await messaging_service.acknowledge_message(
            incident_id=incident_id,
            message_id=message_id,
            actor_id=user_id,
            actor_role=role.upper(),
            actor_name=actor_name,
            notes=payload.notes,
        )
        return ack_msg
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))


# ---------------------------------------------------------------------------
# Reconnect Gap Recovery & Search
# ---------------------------------------------------------------------------

@router.post(
    "/{incident_id}/gap-recovery",
    response_model=MessageGapRecoveryResponse,
    summary="Fetch missing messages during reconnect gap reconciliation",
)
async def recover_message_gaps(
    incident_id: str,
    since_sequence: int = Query(..., ge=0),
    limit: int = Query(100, ge=1, le=200),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    await enforce_incident_access(incident_id, user_id, role)

    return await messaging_service.recover_gap(
        incident_id=incident_id,
        since_sequence=since_sequence,
        limit=limit,
    )


@router.get(
    "/{incident_id}/messages/search",
    response_model=MessageSearchResponse,
    summary="Search messages within incident scope",
)
async def search_incident_messages(
    incident_id: str,
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=100),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    await enforce_incident_access(incident_id, user_id, role)

    return await messaging_service.search_messages(
        incident_id=incident_id,
        query=q,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Participant Management & Presence
# ---------------------------------------------------------------------------

@router.get(
    "/{incident_id}/participants",
    response_model=List[ChannelParticipantRecord],
    summary="List all active channel participants for this incident",
)
async def get_channel_participants(
    incident_id: str,
    include_removed: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    await enforce_incident_access(incident_id, user_id, role)

    return await incident_channel_service.get_participants(
        incident_id=incident_id,
        include_removed=include_removed,
    )


@router.post(
    "/{incident_id}/participants",
    response_model=ChannelParticipantRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Add an authorized participant to the incident channel (Authority only)",
)
async def add_channel_participant(
    incident_id: str,
    payload: ChannelParticipantAddRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "supervisor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authority operators or supervisors may manually add participants",
        )

    try:
        record = await incident_channel_service.add_participant(
            incident_id=incident_id,
            user_id=payload.user_id,
            display_name=payload.display_name,
            role=payload.role,
            responder_role=payload.responder_role,
            permissions=payload.permissions,
        )
        return record
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))


@router.patch(
    "/{incident_id}/participants/{target_user_id}",
    response_model=ChannelParticipantRecord,
    summary="Update participant role, responder_role, or permissions (Authority only)",
)
async def update_channel_participant(
    incident_id: str,
    target_user_id: str,
    payload: ChannelParticipantUpdateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "supervisor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authority operators or supervisors may update participant permissions",
        )

    try:
        return await incident_channel_service.update_participant(
            incident_id=incident_id,
            user_id=target_user_id,
            req=payload,
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))


@router.delete(
    "/{incident_id}/participants/{target_user_id}",
    response_model=ChannelParticipantRecord,
    summary="Remove or restrict a participant from the incident channel (Authority only)",
)
async def remove_channel_participant(
    incident_id: str,
    target_user_id: str,
    reason: Optional[str] = Query(None),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "supervisor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authority operators or supervisors may remove participants",
        )

    try:
        return await incident_channel_service.remove_participant(
            incident_id=incident_id,
            user_id=target_user_id,
            reason=reason,
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))


@router.post(
    "/{incident_id}/presence",
    summary="Update participant presence status (ONLINE, OFFLINE, RECONNECTING)",
)
async def update_participant_presence(
    incident_id: str,
    presence: ParticipantPresenceStatus = Query(ParticipantPresenceStatus.ONLINE),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    await enforce_incident_access(incident_id, user_id, role)

    record = await incident_channel_service.update_presence(
        incident_id=incident_id,
        user_id=user_id,
        presence=presence,
    )
    if not record:
        return {"status": "not_in_channel", "user_id": user_id}
    return {"status": "success", "presence": presence.value, "last_seen_at": record.last_seen_at}


# ---------------------------------------------------------------------------
# Multi-Responder Dispatch Coordination
# ---------------------------------------------------------------------------

@router.post(
    "/{incident_id}/multi-assign",
    summary="Assign an additional responder (Secondary, Specialist, Support) to the live incident",
)
async def multi_responder_assign(
    incident_id: str,
    payload: MultiResponderAssignRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "supervisor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authority operators or supervisors may dispatch multi-responder units",
        )

    try:
        assignment = await assignment_service.create_assignment(
            incident_id=incident_id,
            responder_id=payload.responder_id,
            assigned_by=user_id,
            unit_id=payload.unit_id,
            notes=payload.notes,
            assignment_role=payload.assignment_role,
        )
        return {
            "status": "success",
            "assignment": assignment.model_dump(),
            "assignment_role": payload.assignment_role.value,
        }
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------

@router.post(
    "/{incident_id}/attachments",
    response_model=AttachmentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register and validate an attachment for incident operational communication",
)
async def upload_incident_attachment(
    incident_id: str,
    payload: AttachmentUploadRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    await enforce_incident_access(incident_id, user_id, role)

    try:
        return await messaging_service.register_attachment(
            incident_id=incident_id,
            uploader_id=user_id,
            req=payload,
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))


@router.get(
    "/{incident_id}/attachments/{attachment_id}",
    response_model=AttachmentMetadataRecord,
    summary="Retrieve authorized attachment metadata for incident communication",
)
async def get_incident_attachment(
    incident_id: str,
    attachment_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    await enforce_incident_access(incident_id, user_id, role)

    att = await messaging_service.get_attachment(incident_id=incident_id, attachment_id=attachment_id)
    if not att:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Attachment '{attachment_id}' not found")
    return att
