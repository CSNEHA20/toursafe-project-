"""
TourSafe Responder & Operations REST API Router

Endpoints for:
- Authenticated Responder self-service (profile, availability, real GPS tracking, active assignment)
- Authority Responder Discovery & Management (eligible responders, capability filtering, real distance)
- Unit Management (creation, hierarchy, membership)
- Live Authority Responder Command Map
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..core import database as db_core
from ..routers.auth import get_current_user
from ..schemas.emergency import (
    AssignmentRecord,
    ResponderCapability,
    ResponderCreateRequest,
    ResponderLocationUpdateRequest,
    ResponderRecommendationItem,
    ResponderRecord,
    ResponderSelfProfileResponse,
    ResponderStatus,
    ResponderStatusUpdateRequest,
    ResponderType,
    ResponderUnitCreateRequest,
    ResponderUnitRecord,
    ResponderUnitUpdateRequest,
    ResponderUpdateRequest,
    UnitStatus,
)
from ..services.emergency import (
    assignment_service,
    responder_location_service,
    responder_recommendation_service,
    responder_service,
)

logger = logging.getLogger("toursafe.emergency.responders_router")

router = APIRouter(prefix="/api/v1/responders", tags=["responders"])


def get_database():
    return db_core.get_database()


async def resolve_responder_id(user_id: str, role: str) -> str:
    """
    Resolves responder_id from authenticated user session.
    """
    responder = await responder_service.get_responder_by_user_id(user_id)
    if responder:
        return responder.responder_id
    # If user_id is directly a responder_id
    direct_resp = await responder_service.get_responder(user_id)
    if direct_resp:
        return direct_resp.responder_id
    # Fallback create or return user_id
    return user_id


# ---------------------------------------------------------------------------
# Authenticated Responder Self Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=ResponderSelfProfileResponse,
    summary="Get authenticated responder's operational profile, unit, active assignment, and location state",
)
async def get_my_responder_profile(
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("responder", "authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authenticated responders or operators may access responder self profile",
        )

    responder = await responder_service.get_responder_by_user_id(user_id)
    if not responder:
        responder = await responder_service.get_responder(user_id)
    if not responder:
        # Create a default profile if an authority/responder user logged in without explicit responder record
        now_iso = datetime.now(timezone.utc).isoformat()
        db = get_database()
        u_doc = await db.users.find_one({"id": user_id})
        name = u_doc.get("full_name", f"Responder {user_id[:6]}") if u_doc else f"Responder {user_id[:6]}"
        responder = await responder_service.create_responder(
            ResponderCreateRequest(
                name=name,
                type=ResponderType.FIELD_RESPONDER,
                user_id=user_id,
                capabilities=["FIRST_AID", "SEARCH"],
            )
        )

    # Unit
    unit = None
    if responder.unit_id:
        unit = await responder_service.get_unit(responder.unit_id)

    # Active Assignment
    active_asgn = await assignment_service.get_active_assignment_for_responder(responder.responder_id)

    # Live Location & Freshness
    live_loc = await responder_location_service.get_live_location(responder.responder_id)
    loc_ts = (live_loc or {}).get("timestamp") or responder.last_location_timestamp
    freshness, _ = responder_location_service.calculate_location_freshness(loc_ts)

    return ResponderSelfProfileResponse(
        profile=responder,
        unit=unit,
        active_assignment=active_asgn,
        tracking_active=responder.tracking_active,
        last_location=live_loc or responder.current_location,
        location_freshness=freshness,
    )


@router.post(
    "/me/status",
    response_model=ResponderRecord,
    summary="Update authenticated responder's operational availability state",
)
async def update_my_status(
    payload: ResponderStatusUpdateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("responder", "authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Responder access required")

    responder_id = await resolve_responder_id(user_id, role)
    try:
        return await responder_service.set_responder_status(
            responder_id=responder_id,
            target_status=payload.status,
            reason=payload.reason,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post(
    "/me/location",
    summary="Ingest real GPS coordinates from responder device",
)
async def ingest_my_location(
    payload: ResponderLocationUpdateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("responder", "authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Responder access required")

    responder_id = await resolve_responder_id(user_id, role)
    return await responder_location_service.ingest_responder_location(
        responder_id=responder_id,
        update=payload,
    )


@router.post(
    "/me/tracking/start",
    summary="Start GPS location tracking session on responder device",
)
async def start_my_tracking_session(
    device_id: Optional[str] = Query(None),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("responder", "authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Responder access required")

    responder_id = await resolve_responder_id(user_id, role)
    session_id = await responder_location_service.start_tracking_session(
        responder_id=responder_id,
        device_id=device_id,
    )
    return {"tracking_session_id": session_id, "status": "ACTIVE", "responder_id": responder_id}


@router.post(
    "/me/tracking/stop",
    summary="Stop active GPS location tracking session",
)
async def stop_my_tracking_session(
    session_id: Optional[str] = Query(None),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("responder", "authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Responder access required")

    responder_id = await resolve_responder_id(user_id, role)
    success = await responder_location_service.stop_tracking_session(
        responder_id=responder_id,
        session_id=session_id,
    )
    return {"success": success, "status": "COMPLETED", "responder_id": responder_id}


# ---------------------------------------------------------------------------
# Authority Discovery & Recommendations
# ---------------------------------------------------------------------------

@router.get(
    "/recommendations",
    response_model=List[ResponderRecommendationItem],
    summary="Deterministic eligible responder ranking by capability and geodesic distance (No automatic dispatch)",
)
async def get_responder_recommendations(
    incident_lat: Optional[float] = Query(None),
    incident_lon: Optional[float] = Query(None),
    capabilities: Optional[List[str]] = Query(None),
    type: Optional[ResponderType] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    return await responder_recommendation_service.get_recommendations_for_incident(
        incident_lat=incident_lat,
        incident_lon=incident_lon,
        required_capabilities=capabilities,
        target_type=type,
        max_results=limit,
    )


@router.get(
    "/map/live",
    summary="Authority live responder map dataset with freshness and active assignments",
)
async def get_live_responder_map(
    status_filter: Optional[ResponderStatus] = Query(None),
    type_filter: Optional[ResponderType] = Query(None),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    responders, total = await responder_service.list_responders(
        status=status_filter,
        responder_type=type_filter,
        active_only=True,
        limit=100,
    )

    items = []
    for r in responders:
        live_loc = await responder_location_service.get_live_location(r.responder_id)
        loc = live_loc or r.current_location
        ts = (loc or {}).get("timestamp") or r.last_location_timestamp
        freshness, age = responder_location_service.calculate_location_freshness(ts)

        items.append({
            "responder_id": r.responder_id,
            "name": r.name,
            "type": r.type.value if hasattr(r.type, "value") else str(r.type),
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "unit_id": r.unit_id,
            "capabilities": r.capabilities,
            "location": loc,
            "location_freshness": freshness,
            "location_age_seconds": age,
            "active_assignment_id": r.active_assignment_id,
            "tracking_active": r.tracking_active,
        })

    return {"total": len(items), "responders": items}


# ---------------------------------------------------------------------------
# Unit Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/units",
    summary="List responder operational units",
)
async def list_units(
    status: Optional[UnitStatus] = Query(None),
    type: Optional[ResponderType] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    items, total = await responder_service.list_units(
        status=status,
        unit_type=type,
        active_only=True,
        limit=limit,
        skip=skip,
    )
    return {"total": total, "units": items}


@router.post(
    "/units",
    response_model=ResponderUnitRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new responder operational unit",
)
async def create_unit(
    payload: ResponderUnitCreateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority admin access required")

    return await responder_service.create_unit(payload)


@router.get(
    "/units/{unit_id}",
    response_model=ResponderUnitRecord,
    summary="Get unit details by ID",
)
async def get_unit_by_id(
    unit_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    unit = await responder_service.get_unit(unit_id)
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unit '{unit_id}' not found")
    return unit


@router.put(
    "/units/{unit_id}",
    response_model=ResponderUnitRecord,
    summary="Update operational unit details and membership",
)
async def update_unit_by_id(
    unit_id: str,
    payload: ResponderUnitUpdateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority admin access required")

    unit = await responder_service.update_unit(unit_id, payload)
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unit '{unit_id}' not found")
    return unit


# ---------------------------------------------------------------------------
# Administrative Responder Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "",
    summary="List all registered responders with server-side filters",
)
async def list_responders(
    status: Optional[ResponderStatus] = Query(None),
    type: Optional[ResponderType] = Query(None),
    unit_id: Optional[str] = Query(None),
    capability: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority access required")

    items, total = await responder_service.list_responders(
        status=status,
        responder_type=type,
        unit_id=unit_id,
        capability=capability,
        active_only=True,
        limit=limit,
        skip=skip,
    )
    return {"total": total, "responders": items}


@router.post(
    "",
    response_model=ResponderRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new responder account",
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
    "/{responder_id}",
    response_model=ResponderRecord,
    summary="Get responder record by ID",
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
    "/{responder_id}",
    response_model=ResponderRecord,
    summary="Update responder details",
)
async def update_responder_by_id(
    responder_id: str,
    payload: ResponderUpdateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority admin access required")

    resp = await responder_service.update_responder(responder_id, payload)
    if not resp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Responder '{responder_id}' not found")
    return resp
