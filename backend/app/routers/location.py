from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..core.database import get_database
from ..routers.auth import get_current_user
from ..schemas.location import (
    LiveLocationResponse,
    LocationHistoryListResponse,
    LocationSampleCreate,
    LocationSampleResponse,
    TrackingSessionStartRequest,
    TrackingSessionStopRequest,
    TrackingSessionResponse,
)
from ..services.location_service import location_service

router = APIRouter(tags=["Location"])


async def resolve_tourist_id(user_id: str, role: str) -> str:
    """Helper to resolve the tourist_id corresponding to authenticated user."""
    db = get_database()
    tourist_doc = await db["tourists"].find_one({"user_id": user_id})
    if tourist_doc:
        return tourist_doc.get("id", user_id)
    return user_id


# ─── 1. Ingest Location Update (Tourist) ──────────────────────────────────────

@router.post(
    "/api/v1/location/update",
    response_model=LocationSampleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest GPS Location Sample",
)
async def update_location(
    sample: LocationSampleCreate,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Authenticated endpoint for tourists to transmit real physical device GPS location.
    Validates coordinates, sequence number, and timestamp.
    Derives tourist identity securely from JWT authentication.
    Stores live location in Redis (TTL cache), persists in MongoDB location_history,
    and publishes a realtime 'location.updated' event.
    """
    user_id, role = user_id_role
    if role != "tourist" and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tourist accounts can transmit GPS location updates",
        )

    tourist_id = await resolve_tourist_id(user_id, role)

    try:
        response = await location_service.ingest_location(
            user_id=user_id,
            tourist_id=tourist_id,
            sample=sample,
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process location update: {str(e)}",
        )


# ─── 2. Tracking Session Lifecycle (Tourist) ─────────────────────────────────

@router.post(
    "/api/v1/location/session/start",
    response_model=TrackingSessionResponse,
    summary="Start Location Tracking Session",
)
async def start_tracking_session(
    payload: TrackingSessionStartRequest = TrackingSessionStartRequest(),
    user_id_role: tuple = Depends(get_current_user),
):
    """Start or activate a location tracking session for the authenticated tourist."""
    user_id, role = user_id_role
    if role != "tourist" and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tourist accounts can initiate tracking sessions",
        )

    tourist_id = await resolve_tourist_id(user_id, role)
    return await location_service.start_session(
        user_id=user_id,
        tourist_id=tourist_id,
        device_id=payload.device_id,
        source=payload.source,
    )


@router.post(
    "/api/v1/location/session/stop",
    response_model=TrackingSessionResponse,
    summary="Stop Location Tracking Session",
)
async def stop_tracking_session(
    payload: TrackingSessionStopRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """Stop an active location tracking session."""
    user_id, role = user_id_role
    if role != "tourist" and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tourist accounts can stop tracking sessions",
        )

    tourist_id = await resolve_tourist_id(user_id, role)
    return await location_service.stop_session(
        user_id=user_id,
        tourist_id=tourist_id,
        session_id=payload.session_id,
    )


# ─── 3. Current Location & History for Authenticated Tourist ─────────────────

@router.get(
    "/api/v1/tourists/me/location",
    response_model=LiveLocationResponse,
    summary="Get My Latest Live Location",
)
async def get_my_location(
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Retrieve the current user's latest known location and staleness status (LIVE, RECENT, STALE, UNKNOWN).
    """
    user_id, role = user_id_role
    if role != "tourist" and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tourist profile access required",
        )

    tourist_id = await resolve_tourist_id(user_id, role)
    return await location_service.get_live_location(tourist_id)


@router.get(
    "/api/v1/tourists/me/location-history",
    response_model=LocationHistoryListResponse,
    summary="Get My Location History",
)
async def get_my_location_history(
    start_time: Optional[str] = Query(None, description="Start timestamp ISO8601"),
    end_time: Optional[str] = Query(None, description="End timestamp ISO8601"),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Retrieve historical GPS breadcrumb trails for the authenticated tourist with pagination.
    """
    user_id, role = user_id_role
    if role != "tourist" and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tourist profile access required",
        )

    tourist_id = await resolve_tourist_id(user_id, role)
    items, total = await location_service.get_location_history(
        tourist_id=tourist_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        skip=skip,
    )

    return LocationHistoryListResponse(
        tourist_id=tourist_id,
        items=items,
        total=total,
        limit=limit,
        skip=skip,
    )


# ─── 4. Authority Location Endpoints ─────────────────────────────────────────

@router.get(
    "/api/v1/authority/tourists/{tourist_id}/location",
    response_model=LiveLocationResponse,
    summary="Authority: Get Tourist Live Location",
)
async def get_tourist_location_as_authority(
    tourist_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Authority endpoint to inspect a specific tourist's live location with staleness metrics.
    Requires authority, admin, or responder role.
    """
    _, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or responder access required to view tourist locations",
        )

    return await location_service.get_live_location(tourist_id)


@router.get(
    "/api/v1/authority/tourists/{tourist_id}/location-history",
    response_model=LocationHistoryListResponse,
    summary="Authority: Get Tourist Location History",
)
async def get_tourist_history_as_authority(
    tourist_id: str,
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Authority endpoint to inspect historical GPS track for a specific tourist.
    Requires authority, admin, or responder role.
    """
    _, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or responder access required to view tourist location history",
        )

    items, total = await location_service.get_location_history(
        tourist_id=tourist_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        skip=skip,
    )

    return LocationHistoryListResponse(
        tourist_id=tourist_id,
        items=items,
        total=total,
        limit=limit,
        skip=skip,
    )


@router.get(
    "/api/v1/authority/live-locations",
    response_model=List[LiveLocationResponse],
    summary="Authority: Get All Active Live Tourist Locations",
)
async def get_all_live_locations_as_authority(
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Authority endpoint to stream/poll all current active tourist locations for the Command Map.
    Requires authority, admin, or responder role.
    """
    _, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or responder access required to view live locations",
        )

    return await location_service.get_all_live_locations()
