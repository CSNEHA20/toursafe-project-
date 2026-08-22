"""
TourSafe Authority AI Copilot Router.
Exposes REST endpoints for Copilot Sessions, Grounded Message Conversations,
Action Previews, Human Confirmations, Feedback, and Auditing.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from ..models.copilot import ActionStatus, CopilotSessionStatus
from ..routers.auth import get_current_user, require_role
from ..schemas.copilot import (
    ActionCancelRequest,
    ActionConfirmRequest,
    ActionResponse,
    CopilotMessageCreate,
    CopilotMessageResponse,
    CopilotMetricsResponse,
    CopilotSessionCreate,
    CopilotSessionResponse,
    FeedbackCreate,
    ToolDefinitionSchema,
)
from ..services.copilot.action_manager import action_manager
from ..services.copilot.audit_service import copilot_audit_service
from ..services.copilot.copilot_service import copilot_service
from ..services.copilot.tool_registry import copilot_tool_registry

router = APIRouter(prefix="/api/v1/copilot", tags=["copilot"])


@router.post("/sessions", response_model=CopilotSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_copilot_session(
    payload: CopilotSessionCreate,
    current_user: tuple = Depends(get_current_user),
):
    """Create a new authenticated Copilot operational session."""
    user_id, role = current_user
    if role.lower() not in ["authority", "admin", "dispatcher", "commander"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authorized authority personnel can create Copilot sessions.",
        )

    session = await copilot_service.create_session(
        user_id=user_id,
        title=payload.title or "Authority Operational Assistance",
        active_incident_id=payload.active_incident_id,
        active_zone_id=payload.active_zone_id,
        active_responder_id=payload.active_responder_id,
        metadata=payload.metadata,
    )
    return CopilotSessionResponse(**session.to_dict())


@router.get("/sessions", response_model=List[CopilotSessionResponse])
async def list_copilot_sessions(
    limit: int = Query(default=20, ge=1, le=50),
    current_user: tuple = Depends(get_current_user),
):
    """List Copilot sessions for current authority user."""
    user_id, role = current_user
    sessions = await copilot_service.list_sessions(user_id=user_id, limit=limit)
    return [CopilotSessionResponse(**s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=Dict[str, Any])
async def get_copilot_session(
    session_id: str,
    current_user: tuple = Depends(get_current_user),
):
    """Get session details and full message history."""
    user_id, role = current_user
    session = await copilot_service.get_session(session_id=session_id, user_id=user_id, role=role)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Copilot session not found.")

    messages = await copilot_service.get_messages(session_id=session_id, limit=50)
    return {
        "session": CopilotSessionResponse(**session).model_dump(),
        "messages": messages,
    }


@router.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def delete_copilot_session(
    session_id: str,
    current_user: tuple = Depends(get_current_user),
):
    """Archive or delete a Copilot session."""
    user_id, role = current_user
    session = await copilot_service.get_session(session_id=session_id, user_id=user_id, role=role)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Copilot session not found.")

    from ..core.database import get_database
    db = get_database()
    await db["copilot_sessions"].update_one(
        {"session_id": session_id},
        {"$set": {"status": "archived"}},
    )
    return {"detail": f"Session {session_id} archived successfully."}


@router.post("/sessions/{session_id}/messages", response_model=CopilotMessageResponse)
async def post_copilot_message(
    session_id: str,
    payload: CopilotMessageCreate,
    current_user: tuple = Depends(get_current_user),
):
    """
    Send a natural language question or command to the Copilot.
    Executes intent planning, authorized tools, RAG search, and returns grounded answer.
    """
    user_id, role = current_user
    if role.lower() not in ["authority", "admin", "dispatcher", "commander"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not authorized to access Copilot intelligence.",
        )

    session = await copilot_service.get_session(session_id=session_id, user_id=user_id, role=role)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Copilot session not found.")

    assistant_msg = await copilot_service.process_message(
        session_id=session_id,
        user_id=user_id,
        role=role,
        user_text=payload.content,
        active_incident_id=payload.active_incident_id or session.get("active_incident_id"),
        active_zone_id=payload.active_zone_id or session.get("active_zone_id"),
        active_responder_id=payload.active_responder_id or session.get("active_responder_id"),
        organization_id=session.get("organization_id"),
        jurisdiction_id=session.get("jurisdiction_id"),
    )

    return CopilotMessageResponse(**assistant_msg.to_dict())


@router.post("/actions/{action_id}/confirm", response_model=ActionResponse)
async def confirm_copilot_action(
    action_id: str,
    payload: ActionConfirmRequest,
    current_user: tuple = Depends(get_current_user),
):
    """
    Human-in-the-loop confirmation for an AI-proposed operational action.
    Validates confirmation token, authorization role, and idempotency.
    """
    user_id, role = current_user
    action = await action_manager.get_action(action_id)
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action proposal not found.")

    result = await action_manager.confirm_action(
        action_id=action_id,
        confirmation_token=payload.confirmation_token,
        confirmed_by_user_id=user_id,
        confirmed_by_role=role,
        idempotency_key=payload.idempotency_key,
    )

    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message"))

    # Log audit event
    await copilot_audit_service.log_event(
        user_id=user_id,
        session_id=action.get("session_id", ""),
        role=role,
        action="action_confirmed",
        tool_name=action.get("tool_name"),
        confirmation_token=payload.confirmation_token,
        result_summary=result.get("message"),
        authorization_passed=True,
    )

    return ActionResponse(
        action_id=action_id,
        session_id=action.get("session_id", ""),
        tool_name=action.get("tool_name", ""),
        action_type=action.get("action_type", ""),
        target_id=action.get("target_id", ""),
        status=ActionStatus.CONFIRMED,
        confirmed_by=user_id,
        execution_result=result.get("execution_result"),
        message=result.get("message", "Action confirmed."),
    )


@router.post("/actions/{action_id}/cancel", response_model=ActionResponse)
async def cancel_copilot_action(
    action_id: str,
    payload: ActionCancelRequest,
    current_user: tuple = Depends(get_current_user),
):
    """Cancel an AI-proposed operational action without executing side-effects."""
    user_id, role = current_user
    action = await action_manager.get_action(action_id)
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action proposal not found.")

    result = await action_manager.cancel_action(
        action_id=action_id,
        cancelled_by_user_id=user_id,
        reason_note=payload.reason_note,
    )

    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message"))

    # Log audit event
    await copilot_audit_service.log_event(
        user_id=user_id,
        session_id=action.get("session_id", ""),
        role=role,
        action="action_cancelled",
        tool_name=action.get("tool_name"),
        result_summary=result.get("message"),
        authorization_passed=True,
    )

    return ActionResponse(
        action_id=action_id,
        session_id=action.get("session_id", ""),
        tool_name=action.get("tool_name", ""),
        action_type=action.get("action_type", ""),
        target_id=action.get("target_id", ""),
        status=ActionStatus.CANCELLED,
        message=result.get("message", "Action cancelled."),
    )


@router.post("/messages/{message_id}/feedback", status_code=status.HTTP_200_OK)
async def submit_message_feedback(
    message_id: str,
    payload: FeedbackCreate,
    current_user: tuple = Depends(get_current_user),
):
    """Submit quality feedback (HELPFUL, NOT_HELPFUL, INCORRECT, OUTDATED) for an AI response."""
    user_id, role = current_user
    from ..core.database import get_database
    db = get_database()
    msg = await db["copilot_messages"].find_one({"message_id": message_id})
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    fb = await copilot_audit_service.record_feedback(
        message_id=message_id,
        session_id=msg.get("session_id", ""),
        user_id=user_id,
        rating=payload.rating,
        reason=payload.reason,
    )
    return {"status": "success", "feedback_id": fb.feedback_id}


@router.get("/tools", response_model=List[ToolDefinitionSchema])
async def list_authorized_tools(
    current_user: tuple = Depends(get_current_user),
):
    """List all authorized tools and schemas available to current authority role."""
    user_id, role = current_user
    authorized = copilot_tool_registry.get_authorized_tools_for_role(role)
    return [
        ToolDefinitionSchema(
            name=t.name,
            category=t.category,
            description=t.description,
            parameters=t.parameters,
            required_role=t.required_roles,
            read_only=t.read_only,
            requires_preview=t.requires_preview,
        )
        for t in authorized
    ]


@router.get("/metrics", response_model=CopilotMetricsResponse)
async def get_copilot_metrics(
    current_user: tuple = Depends(get_current_user),
):
    """Retrieve aggregate Copilot performance, latency, tool calls, and feedback metrics."""
    user_id, role = current_user
    if role.lower() not in ["authority", "admin", "commander"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required for metrics.")
    metrics = await copilot_audit_service.get_metrics()
    return CopilotMetricsResponse(**metrics)


@router.get("/audit", response_model=List[Dict[str, Any]])
async def get_copilot_audit_logs(
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: tuple = Depends(get_current_user),
):
    """Retrieve immutable Copilot audit event log."""
    user_id, role = current_user
    if role.lower() not in ["authority", "admin", "commander"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required for audit logs.")
    events = await copilot_audit_service.query_audit_logs(session_id=session_id, limit=limit)
    return events
