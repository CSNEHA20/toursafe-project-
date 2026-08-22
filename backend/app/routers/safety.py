"""
TourSafe Safety & Incident Management REST API Endpoints

Authority Endpoints:
- GET /api/v1/authority/tourists/{tourist_id}/safety
- GET /api/v1/authority/tourists/{tourist_id}/safety/risk-assessment
- POST /api/v1/authority/safety/evaluate
- GET /api/v1/authority/safety/risk-matrix
- GET /api/v1/authority/tourists/{tourist_id}/safety/history
- GET /api/v1/authority/tourists/{tourist_id}/incidents
- GET /api/v1/authority/incidents
- GET /api/v1/authority/incidents/{incident_id}
- POST /api/v1/authority/incidents/{incident_id}/acknowledge
- POST /api/v1/authority/incidents/{incident_id}/resolve

Tourist Endpoints:
- GET /api/v1/tourists/me/safety
- POST /api/v1/tourists/me/safety/check-response
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..core.database import get_database
from ..routers.auth import get_current_user
from ..schemas.safety import (
    AuthoritySafetyStatusResponse,
    ConfidenceClass,
    IncidentAcknowledgeRequest,
    IncidentListResponse,
    IncidentRecord,
    IncidentResolveRequest,
    MultiSignalRiskAssessment,
    RiskMatrixConfigResponse,
    SafetyCheckResponseRequest,
    SafetyCheckResponseResult,
    SafetyDecision,
    SafetyHistoryResponse,
    SafetySignal,
    SafetyState,
    TouristSafetyStatusResponse,
)
from ..services.safety import (
    safety_config,
    safety_orchestrator,
    safety_redis_state,
    safety_repository,
)
from ..services.safety.events import map_tourist_guidance
from ..services.safety.fusion import risk_fusion_engine

logger = logging.getLogger("toursafe.safety.router")

router = APIRouter(tags=["safety"])


# Request payload for simulated evaluation
class SafetyEvaluateRequest(BaseModel):
    tourist_id: str
    signals: List[SafetySignal]
    context: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Authority Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/authority/tourists/{tourist_id}/safety",
    response_model=AuthoritySafetyStatusResponse,
    summary="Get active safety state and fused signals for a tourist",
)
async def get_tourist_safety_authority(
    tourist_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority access required for safety telemetry inspection",
        )

    active_state = await safety_redis_state.get_active_state(tourist_id)
    active_inc = None
    if active_state and active_state.active_incident_id:
        active_inc = await safety_repository.get_incident_by_id(active_state.active_incident_id)

    if not active_state:
        # Default UNKNOWN snapshot if no tracking/safety state exists
        now_iso = datetime.now(timezone.utc).isoformat()
        return AuthoritySafetyStatusResponse(
            tourist_id=tourist_id,
            current_state=SafetyState.UNKNOWN,
            previous_state=SafetyState.UNKNOWN,
            decision_id="none",
            started_at=now_iso,
            last_update=now_iso,
            rule_version=safety_config.rule_version,
            confidence_class=ConfidenceClass.UNKNOWN,
            active_reasons=["No telemetry or safety data received yet"],
            active_signals={},
            active_incident=None,
            risk_score=0.0,
            risk_assessment=None,
        )

    return AuthoritySafetyStatusResponse(
        tourist_id=tourist_id,
        current_state=active_state.current_state,
        previous_state=active_state.previous_state,
        decision_id=active_state.decision_id,
        started_at=active_state.started_at,
        last_update=active_state.last_update,
        rule_version=active_state.rule_version,
        confidence_class=active_state.confidence_class,
        active_reasons=active_state.active_reasons,
        active_signals=active_state.active_signals_summary,
        active_incident=active_inc,
        recovery_started_at=active_state.recovery_started_at,
        risk_score=active_state.risk_score,
        risk_assessment=active_state.risk_assessment,
    )


@router.get(
    "/api/v1/authority/tourists/{tourist_id}/safety/risk-assessment",
    response_model=MultiSignalRiskAssessment,
    summary="Get deep multi-signal risk fusion assessment for a tourist",
)
async def get_tourist_risk_assessment(
    tourist_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority access required",
        )

    active_state = await safety_redis_state.get_active_state(tourist_id)
    if active_state and active_state.risk_assessment:
        return active_state.risk_assessment

    # If no cached assessment, generate live from active signals
    signals = await safety_redis_state.get_active_signals(tourist_id)
    assessment = risk_fusion_engine.evaluate_risk_fusion(
        tourist_id=tourist_id,
        session_id=None,
        active_signals=signals,
    )
    return assessment


@router.post(
    "/api/v1/authority/safety/evaluate",
    response_model=MultiSignalRiskAssessment,
    summary="Evaluate multi-signal risk fusion on-demand for simulated or historical signal payloads",
)
async def evaluate_safety_signals_on_demand(
    payload: SafetyEvaluateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority access required",
        )

    assessment = await safety_orchestrator.evaluate_simulated_signals(
        tourist_id=payload.tourist_id,
        signals=payload.signals,
        context=payload.context,
    )
    return assessment


@router.get(
    "/api/v1/authority/safety/risk-matrix",
    response_model=RiskMatrixConfigResponse,
    summary="Inspect active risk fusion matrix configuration, weights, and correlation signatures",
)
async def get_risk_matrix_config(
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority admin access required",
        )

    signatures = [
        {"signature_id": "SIGNATURE_TRANSIT_VIBRATION", "pattern": "BENIGN_HIGHWAY_TRANSIT_ROUGH_ROAD", "dampening": 0.30, "action": "Suppresses transit false alarm"},
        {"signature_id": "SIGNATURE_ISOLATED_IMPACT_SPIKE", "pattern": "TRANSIENT_PHONE_DROP", "dampening": 0.25, "action": "Suppresses single-frame drop shock"},
        {"signature_id": "SIGNATURE_POWER_SAVING_PACKET_LOSS", "pattern": "DEVICE_BATTERY_SAVING_MODE", "dampening": 0.40, "action": "Gates low-battery telemetry drop"},
        {"signature_id": "SIGNATURE_DAYTIME_AMENITY_STOP", "pattern": "BENIGN_REST_STOP_DETOUR", "dampening": 0.50, "action": "Dampens minor daytime stop detour"},
        {"signature_id": "SIGNATURE_HIGH_G_DECELERATION_IMPACT", "pattern": "CORROBORATED_VEHICULAR_CRASH", "dampening": 1.0, "action": "Urgent emergency response escalation"},
        {"signature_id": "SIGNATURE_HAZARD_ZONE_IMPACT", "pattern": "CORROBORATED_HAZARD_FALL", "dampening": 1.0, "action": "Urgent trail fall response escalation"},
        {"signature_id": "SIGNATURE_NOCTURNAL_OFF_CORRIDOR", "pattern": "NIGHT_OFF_ROUTE_ISOLATION", "dampening": 1.0, "action": "High-priority proactive safety check"},
    ]

    return RiskMatrixConfigResponse(
        rule_version=safety_config.rule_version,
        weights={
            "motion": safety_config.weight_motion,
            "spatial": safety_config.weight_spatial,
            "itinerary": safety_config.weight_itinerary,
            "environmental": safety_config.weight_environmental,
            "vulnerability": safety_config.weight_vulnerability,
        },
        thresholds={
            "watch": safety_config.risk_threshold_watch,
            "elevated": safety_config.risk_threshold_elevated,
            "candidate": safety_config.risk_threshold_candidate,
            "incident": safety_config.risk_threshold_incident,
        },
        correlation_signatures=signatures,
        dampening_factors={
            "transit_road_roughness": 0.30,
            "transient_phone_drop": 0.25,
            "battery_saving_drop": 0.40,
            "benign_rest_stop": 0.50,
            "user_confirmed_safe": 0.20,
        },
        zone_risk_levels=safety_config.zone_risk_levels,
    )


@router.get(
    "/api/v1/authority/tourists/{tourist_id}/safety/history",
    response_model=SafetyHistoryResponse,
    summary="Get immutable safety decision history and audit trail for a tourist",
)
async def get_tourist_safety_history(
    tourist_id: str,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority access required for safety audit history",
        )

    decisions, total = await safety_repository.get_decision_history(tourist_id=tourist_id, limit=limit, skip=skip)
    return SafetyHistoryResponse(
        tourist_id=tourist_id,
        decisions=decisions,
        total=total,
    )


@router.get(
    "/api/v1/authority/tourists/{tourist_id}/incidents",
    response_model=IncidentListResponse,
    summary="Get incidents for a specific tourist",
)
async def get_tourist_incidents(
    tourist_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority access required",
        )

    items, total = await safety_repository.list_incidents(tourist_id=tourist_id, limit=limit, page=page)
    return IncidentListResponse(incidents=items, total=total, page=page, limit=limit)


@router.get(
    "/api/v1/authority/incidents",
    response_model=IncidentListResponse,
    summary="Query safety incidents with filtering and pagination",
)
async def list_all_incidents(
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = Query(None),
    tourist_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority access required",
        )

    items, total = await safety_repository.list_incidents(
        status=status_filter,
        severity=severity,
        tourist_id=tourist_id,
        limit=limit,
        page=page,
    )
    return IncidentListResponse(incidents=items, total=total, page=page, limit=limit)


@router.get(
    "/api/v1/authority/incidents/{incident_id}",
    response_model=IncidentRecord,
    summary="Get incident details by ID",
)
async def get_incident_by_id(
    incident_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority access required",
        )

    inc = await safety_repository.get_incident_by_id(incident_id)
    if not inc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return inc


@router.post(
    "/api/v1/authority/incidents/{incident_id}/acknowledge",
    response_model=IncidentRecord,
    summary="Acknowledge an active incident",
)
async def acknowledge_incident(
    incident_id: str,
    payload: IncidentAcknowledgeRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority access required",
        )

    try:
        updated = await safety_orchestrator.acknowledge_incident(
            incident_id=incident_id,
            authority_id=user_id,
            notes=payload.notes,
        )
        return updated
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post(
    "/api/v1/authority/incidents/{incident_id}/resolve",
    response_model=IncidentRecord,
    summary="Resolve an incident with mandatory reason",
)
async def resolve_incident(
    incident_id: str,
    payload: IncidentResolveRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority access required",
        )

    try:
        updated = await safety_orchestrator.resolve_incident(
            incident_id=incident_id,
            resolution_reason=payload.resolution_reason,
            authority_id=user_id,
            notes=payload.notes,
        )
        return updated
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


# ---------------------------------------------------------------------------
# Tourist Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/tourists/me/safety",
    response_model=TouristSafetyStatusResponse,
    summary="Get sanitized, user-appropriate safety status for the authenticated tourist",
)
async def get_tourist_safety_me(
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tourist profile required",
        )

    active_state = await safety_redis_state.get_active_state(user_id)

    # If not found by user_id, check by profile id
    if not active_state:
        try:
            db = get_database()
            tourist_doc = await db.tourists.find_one({"user_id": user_id})
            if tourist_doc and tourist_doc.get("id"):
                active_state = await safety_redis_state.get_active_state(tourist_doc.get("id"))
        except Exception:
            pass

    now_iso = datetime.now(timezone.utc).isoformat()

    if not active_state:
        return TouristSafetyStatusResponse(
            safety_status="Normal",
            monitoring_active=False,
            gps_connected=False,
            last_checked_at=now_iso,
            guidance_message="Start a tracking session to enable real-time safety monitoring.",
            safety_index=100.0,
            risk_level="SAFE",
            proactive_check_required=False,
        )

    guidance, status_label = map_tourist_guidance(active_state.current_state, active_state.active_reasons)
    zone_info = active_state.active_signals_summary.get("ZONE_ENTERED") or active_state.active_signals_summary.get("ZONE_DWELL")
    zone_name = zone_info.get("zone_name") if isinstance(zone_info, dict) else None
    zone_risk = zone_info.get("risk_level") if isinstance(zone_info, dict) else None

    # Calculate friendly safety index (100 is completely safe)
    composite_risk = active_state.risk_score or 0.0
    safety_idx = max(0.0, 100.0 - composite_risk)

    proactive_check = False
    proactive_msg = None
    if active_state.risk_assessment:
        rec = active_state.risk_assessment.decision_support.recommended_action
        if rec == "PROACTIVE_SAFETY_CHECK":
            proactive_check = True
            proactive_msg = active_state.risk_assessment.explainability.tourist_guidance

    return TouristSafetyStatusResponse(
        safety_status=status_label,
        monitoring_active=active_state.current_state != SafetyState.UNKNOWN,
        gps_connected=active_state.confidence_class != ConfidenceClass.UNKNOWN,
        last_checked_at=active_state.last_update,
        zone_name=zone_name,
        zone_risk=zone_risk,
        guidance_message=active_state.risk_assessment.explainability.tourist_guidance if active_state.risk_assessment else guidance,
        safety_index=round(safety_idx, 1),
        risk_level=active_state.risk_assessment.risk_breakdown.risk_level_label if active_state.risk_assessment else "SAFE",
        proactive_check_required=proactive_check,
        proactive_check_message=proactive_msg,
    )


@router.post(
    "/api/v1/tourists/me/safety/check-response",
    response_model=SafetyCheckResponseResult,
    summary="Submit a tourist response to an active safety check prompt (Confirm Safe / Request Assistance)",
)
async def submit_tourist_safety_check(
    payload: SafetyCheckResponseRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tourist profile required",
        )

    # Determine tourist identifier
    tourist_id = user_id
    try:
        db = get_database()
        tourist_doc = await db.tourists.find_one({"user_id": user_id})
        if tourist_doc and tourist_doc.get("id"):
            tourist_id = tourist_doc.get("id")
    except Exception:
        pass

    result = await safety_orchestrator.handle_safety_check_response(
        tourist_id=tourist_id,
        payload=payload,
    )
    return result
