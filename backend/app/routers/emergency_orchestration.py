"""
TourSafe Emergency Response Automation & Escalation Orchestration Router

Provides endpoints for:
- Response Policy authoring, validation, approval, activation, rollback, and simulation sandbox
- Response Plan tracking, action execution, and SLA monitoring
- Human-in-the-loop controls (pause, resume, manual override, reassign, cancel)
- Scheduler sweep triggers, health diagnostics, and real KPI aggregations
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..routers.auth import get_current_user
from ..schemas.emergency import (
    AutomationPauseRequest,
    AutomationResumeRequest,
    ManualOverrideRequest,
    OrchestratorHealthResponse,
    PolicyApproveRequest,
    PolicyCreateRequest,
    PolicyRollbackRequest,
    PolicySimulationRequest,
    PolicySimulationResult,
    PolicyStatus,
    PolicyTriggerType,
    PolicyUpdateRequest,
    ResponseKpiResponse,
    ResponsePlanCancelRequest,
    ResponsePlanDetailResponse,
    ResponsePolicy,
)
from ..services.emergency.response_orchestrator import response_orchestrator
from ..services.emergency.response_policy_service import response_policy_service

logger = logging.getLogger("toursafe.routers.emergency_orchestration")

router = APIRouter(
    prefix="/api/v1/orchestration",
    tags=["Emergency Response Orchestration"],
)


# ---------------------------------------------------------------------------
# Policy Management & Simulation
# ---------------------------------------------------------------------------

@router.get("/policies", response_model=List[ResponsePolicy])
async def list_policies(
    trigger_type: Optional[PolicyTriggerType] = None,
    status: Optional[PolicyStatus] = None,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Lists all response policies with optional trigger and status filters.
    Requires authority, supervisor, or admin role.
    """
    user_id, role = user_id_role
    if role not in ("authority", "admin", "supervisor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only authority operators and supervisors can access response policies.",
        )
    return await response_policy_service.list_policies(trigger_type=trigger_type, status=status)


@router.post("/policies", response_model=ResponsePolicy, status_code=status.HTTP_201_CREATED)
async def create_policy(
    req: PolicyCreateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Creates a new draft response policy. Strictly validates all stages, timeouts, and actions.
    Requires admin or supervisor role.
    """
    user_id, role = user_id_role
    if role not in ("admin", "supervisor", "authority"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin or supervisor role required to create policies.",
        )
    try:
        return await response_policy_service.create_policy(req, user_id=str(user_id))
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(val_err))


@router.get("/policies/{policy_id}", response_model=ResponsePolicy)
async def get_policy(
    policy_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Retrieves a response policy by ID.
    """
    user_id, role = user_id_role
    if role not in ("authority", "admin", "supervisor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    policy = await response_policy_service.get_policy_by_id(policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Policy '{policy_id}' not found")
    return policy


@router.put("/policies/{policy_id}", response_model=ResponsePolicy)
async def update_policy(
    policy_id: str,
    req: PolicyUpdateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Updates an existing DRAFT or TESTING response policy.
    Active production policies cannot be mutated directly.
    """
    user_id, role = user_id_role
    if role not in ("admin", "supervisor", "authority"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    try:
        return await response_policy_service.update_policy(policy_id, req, user_id=str(user_id))
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))


@router.post("/policies/{policy_id}/approve", response_model=ResponsePolicy)
async def approve_policy(
    policy_id: str,
    req: PolicyApproveRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Approves a policy for production activation.
    Requires supervisor or admin role.
    """
    user_id, role = user_id_role
    if role not in ("admin", "supervisor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only supervisors or administrators can approve production response policies.",
        )
    try:
        return await response_policy_service.approve_policy(policy_id, user_id=str(user_id), reason=req.reason)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))


@router.post("/policies/{policy_id}/activate", response_model=ResponsePolicy)
async def activate_policy(
    policy_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Activates an APPROVED response policy. Automatically retires the existing active policy for the same trigger.
    Requires admin or supervisor role.
    """
    user_id, role = user_id_role
    if role not in ("admin", "supervisor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    try:
        return await response_policy_service.activate_policy(policy_id, user_id=str(user_id))
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))


@router.post("/policies/rollback", response_model=ResponsePolicy)
async def rollback_policy(
    req: PolicyRollbackRequest,
    trigger_type: PolicyTriggerType = Query(PolicyTriggerType.SAFETY_STATE),
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Rolls back the active policy to a previously approved version.
    """
    user_id, role = user_id_role
    if role not in ("admin", "supervisor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    try:
        return await response_policy_service.rollback_policy(
            trigger_type=trigger_type,
            target_version=req.target_version,
            user_id=str(user_id),
            reason=req.reason,
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))


@router.post("/policies/simulate", response_model=PolicySimulationResult)
async def simulate_policy(
    req: PolicySimulationRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Dry-run simulation sandbox for response policies.
    Evaluates action dependency graphs, stage escalations, and projected timelines
    without producing real incidents, dispatches, or notifications.
    """
    user_id, role = user_id_role
    if role not in ("authority", "admin", "supervisor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    target_policy = None
    if req.policy_id:
        target_policy = await response_policy_service.get_policy_by_id(req.policy_id)

    return response_policy_service.simulate_policy(req, target_policy=target_policy)


# ---------------------------------------------------------------------------
# Response Plan Operations & Human-in-the-Loop Controls
# ---------------------------------------------------------------------------

@router.get("/plans/{incident_id}", response_model=ResponsePlanDetailResponse)
async def get_response_plan_for_incident(
    incident_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Retrieves full response plan details, active timers, actions, and SLA status for an incident.
    """
    detail = await response_orchestrator.get_plan_by_incident(incident_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No response plan found for incident '{incident_id}'")
    return detail


@router.post("/plans/{plan_id}/override")
async def manual_override(
    plan_id: str,
    req: ManualOverrideRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Executes an authorized operator override (force escalation, reassignment, status override).
    Requires authority, supervisor, or admin role.
    """
    user_id, role = user_id_role
    if role not in ("authority", "supervisor", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    try:
        updated = await response_orchestrator.manual_override(plan_id, user_id=str(user_id), req=req)
        return {"status": "SUCCESS", "plan": updated}
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))


@router.post("/plans/{plan_id}/pause")
async def pause_automation(
    plan_id: str,
    req: AutomationPauseRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Pauses automated timers and escalation actions for a response plan.
    """
    user_id, role = user_id_role
    if role not in ("authority", "supervisor", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    try:
        updated = await response_orchestrator.pause_automation(plan_id, user_id=str(user_id), reason=req.reason)
        return {"status": "AUTOMATION_PAUSED", "plan": updated}
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))


@router.post("/plans/{plan_id}/resume")
async def resume_automation(
    plan_id: str,
    req: AutomationResumeRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Resumes automation for a paused response plan and re-evaluates ready actions.
    """
    user_id, role = user_id_role
    if role not in ("authority", "supervisor", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    try:
        updated = await response_orchestrator.resume_automation(plan_id, user_id=str(user_id), reason=req.reason)
        return {"status": "AUTOMATION_RESUMED", "plan": updated}
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))


@router.post("/plans/{plan_id}/actions/{action_id}/retry")
async def retry_action(
    plan_id: str,
    action_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Manually retries a failed response action.
    """
    user_id, role = user_id_role
    if role not in ("authority", "supervisor", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    res = await response_orchestrator.execute_single_action(plan_id, action_id)
    return res


# ---------------------------------------------------------------------------
# Diagnostics, Health, Scheduler & KPIs
# ---------------------------------------------------------------------------

@router.get("/health", response_model=OrchestratorHealthResponse)
async def get_orchestrator_health(
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Returns diagnostic health metrics for response orchestrator, timer queue, and external adapters.
    """
    return await response_orchestrator.get_health()


@router.get("/kpis", response_model=ResponseKpiResponse)
async def get_response_kpis(
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Returns calculated response KPIs across recorded response plans.
    """
    return await response_orchestrator.get_kpis()


@router.post("/sweep")
async def trigger_scheduler_sweep(
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Manually triggers a scheduler sweep across pending timer jobs.
    """
    user_id, role = user_id_role
    if role not in ("authority", "supervisor", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    processed = await response_orchestrator.run_scheduler_sweep()
    return {"status": "SUCCESS", "processed_timer_jobs": processed, "timestamp": datetime.now(timezone.utc).isoformat()}
