"""
TourSafe - Geofencing Endpoints Router

Provides:
1. Tourist endpoints:
   - GET /api/v1/tourists/me/zones/current (Active zones, risk levels, dwell duration)
   - GET /api/v1/tourists/me/zones/history (Paginated transition history)
2. Authority endpoints:
   - GET /api/v1/authority/tourists/{tourist_id}/zones/current
   - GET /api/v1/authority/tourists/{tourist_id}/zones/history
   - GET /api/v1/authority/zones/live-occupancy
3. Dev Diagnostics:
   - GET /api/v1/dev/geofence/diagnostics/{tourist_id}
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..core import database as db_core
from ..routers.auth import get_current_user, require_role
from ..services.geofencing import (
    ActiveZoneMembership,
    GeofenceDiagnostics,
    TouristGeofenceSnapshot,
    ZoneTransitionRecord,
    geofence_engine,
    geofence_repository,
)

router = APIRouter(tags=["Geofencing"])


async def resolve_tourist_id(user_id: str, role: str) -> str:
    """Helper to resolve tourist profile ID for authenticated user."""
    db = db_core.get_database()
    tourist_doc = await db["tourists"].find_one({"user_id": user_id})
    if tourist_doc:
        return tourist_doc.get("id", user_id)
    return user_id


# ─── 1. Tourist Zone Endpoints ────────────────────────────────────────────────

@router.get(
    "/api/v1/tourists/me/zones/current",
    response_model=TouristGeofenceSnapshot,
    summary="Get My Current Active Safety Zones",
)
async def get_my_current_zones(
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Returns current active zone memberships, dwell time, and highest risk level
    for the authenticated tourist.
    """
    user_id, role = user_id_role
    if role not in ("tourist", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tourist profile access required",
        )

    tourist_id = await resolve_tourist_id(user_id, role)
    snapshot = await geofence_engine.get_tourist_snapshot(tourist_id)
    return snapshot


@router.get(
    "/api/v1/tourists/me/zones/history",
    summary="Get My Zone Transition History",
)
async def get_my_zone_history(
    start_time: Optional[str] = Query(None, description="Start timestamp ISO8601"),
    end_time: Optional[str] = Query(None, description="End timestamp ISO8601"),
    zone_id: Optional[str] = Query(None, description="Filter by zone ID"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Paginated audit history of zone entries, exits, and dwell events for authenticated tourist.
    """
    user_id, role = user_id_role
    if role not in ("tourist", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tourist profile access required",
        )

    tourist_id = await resolve_tourist_id(user_id, role)
    records, total = await geofence_repository.get_tourist_transition_history(
        tourist_id=tourist_id,
        start_time=start_time,
        end_time=end_time,
        zone_id=zone_id,
        limit=limit,
        skip=skip,
    )

    return {
        "tourist_id": tourist_id,
        "items": [r.model_dump() for r in records],
        "total": total,
        "limit": limit,
        "skip": skip,
    }


# ─── 2. Authority Zone Endpoints ──────────────────────────────────────────────

@router.get(
    "/api/v1/authority/tourists/{tourist_id}/zones/current",
    response_model=TouristGeofenceSnapshot,
    summary="Authority: Get Tourist Active Zones",
)
async def get_tourist_zones_as_authority(
    tourist_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Authority endpoint to inspect real-time zone memberships and dwell metrics for a tourist.
    """
    _, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or responder credentials required",
        )

    snapshot = await geofence_engine.get_tourist_snapshot(tourist_id)
    return snapshot


@router.get(
    "/api/v1/authority/tourists/{tourist_id}/zones/history",
    summary="Authority: Get Tourist Zone Transition History",
)
async def get_tourist_zone_history_as_authority(
    tourist_id: str,
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Authority endpoint to inspect historical zone audit log for a tourist.
    """
    _, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or responder credentials required",
        )

    records, total = await geofence_repository.get_tourist_transition_history(
        tourist_id=tourist_id,
        start_time=start_time,
        end_time=end_time,
        zone_id=zone_id,
        limit=limit,
        skip=skip,
    )

    return {
        "tourist_id": tourist_id,
        "items": [r.model_dump() for r in records],
        "total": total,
        "limit": limit,
        "skip": skip,
    }


@router.get(
    "/api/v1/authority/zones/live-occupancy",
    summary="Authority: Get Live Zone Occupancy Summary",
)
async def get_live_zone_occupancy_as_authority(
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Authority Command Map endpoint returning active tourist count and risk summary for all zones.
    """
    _, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or responder credentials required",
        )

    all_zones = await geofence_repository.get_all_active_zones()
    zone_summaries = []

    for z in all_zones:
        zid = z.get("zone_id") or z.get("id") or str(z.get("_id", ""))
        zone_summaries.append({
            "zone_id": zid,
            "name": z.get("name"),
            "zone_type": z.get("zone_type", "safe"),
            "risk_level": z.get("risk_level", "low"),
            "active_tourists_count": 0,
            "center": z.get("center"),
            "boundary": z.get("boundary"),
        })

    return {
        "total_active_zones": len(zone_summaries),
        "zones": zone_summaries,
    }


# ─── 3. Dev Geofence Diagnostics ──────────────────────────────────────────────

@router.get(
    "/api/v1/dev/geofence/diagnostics/{tourist_id}",
    summary="Dev: Geofence Engine Diagnostics",
)
async def get_geofence_diagnostics(
    tourist_id: str,
):
    """
    Development-only endpoint returning detailed geometry calculations, candidate zones,
    boundary distances, and hysteresis state machine diagnostics.
    """
    diag = geofence_engine.get_diagnostics(tourist_id)
    if not diag:
        # Fallback snapshot
        snapshot = await geofence_engine.get_tourist_snapshot(tourist_id)
        return {
            "tourist_id": tourist_id,
            "status": "idle",
            "active_zones": [m.model_dump() for m in snapshot.active_zones],
            "highest_risk_level": snapshot.highest_risk_level,
            "message": "No active telemetry processed yet in current session",
        }

    return diag.model_dump()
