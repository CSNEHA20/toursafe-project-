from fastapi import APIRouter, Depends, HTTPException, status
from ..core.database import get_database
from ..routers.auth import get_current_user
from ..schemas.itinerary import ItineraryCreate, ItineraryUpdate, ItineraryResponse, ItineraryList
from ..models.itinerary import Itinerary
from typing import List


router = APIRouter(prefix="/api/v1/tourists", tags=["tourists-itinerary"])


@router.get("/me/itinerary", response_model=ItineraryList)
async def list_itineraries(
    user_id_role: tuple = Depends(get_current_user),
):
    """List itineraries for authenticated tourist."""
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Itinerary access required",
        )

    db = get_database()
    itineraries_col = db["itineraries"]
    items = await itineraries_col.find({"tourist_id": user_id}).sort("created_at", -1).to_list(length=None)

    result_items = []
    for it in items:
        result_items.append(ItineraryResponse(
            id=it["id"],
            tourist_id=it["tourist_id"],
            title=it["title"],
            destination=it.get("destination"),
            start_date=it.get("start_date"),
            end_date=it.get("end_date"),
            notes=it.get("notes"),
            status=it.get("status", "active"),
            created_at=it.get("created_at"),
            updated_at=it.get("updated_at"),
        ))

    return ItineraryList(
        items=result_items,
        total=len(result_items),
        page=1,
        per_page=len(result_items),
    )


@router.post("/me/itinerary", response_model=ItineraryResponse, status_code=status.HTTP_201_CREATED)
async def create_itinerary(
    data: ItineraryCreate,
    user_id_role: tuple = Depends(get_current_user),
):
    """Create a new itinerary. Authenticated tourist only."""
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Itinerary creation required",
        )

    db = get_database()
    itineraries_col = db["itineraries"]

    itinerary = Itinerary(
        id="",
        tourist_id=user_id,
        title=data.title,
        destination=data.destination,
        start_date=data.start_date,
        end_date=data.end_date,
        notes=data.notes,
        entries=data.stops,
    )
    await itineraries_col.insert_one(itinerary.to_dict())

    return ItineraryResponse(
        id=itinerary.id,
        tourist_id=itinerary.tourist_id,
        title=itinerary.title,
        destination=itinerary.destination,
        start_date=itinerary.start_date,
        end_date=itinerary.end_date,
        notes=itinerary.notes,
        status=itinerary.status,
        created_at=itinerary.created_at,
        updated_at=itinerary.updated_at,
    )


@router.patch("/me/itinerary/{itinerary_id}", response_model=ItineraryResponse)
async def update_itinerary(
    itinerary_id: str,
    data: ItineraryUpdate,
    user_id_role: tuple = Depends(get_current_user),
):
    """Update an itinerary. Authenticated tourist only."""
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Itinerary update required",
        )

    db = get_database()
    itineraries_col = db["itineraries"]

    # Verify ownership
    existing = await itineraries_col.find_one({"tourist_id": user_id, "id": itinerary_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Itinerary not found or access denied",
        )

    # Build update data
    update_data = {}
    if data.title is not None:
        update_data["title"] = data.title
    if data.destination is not None:
        update_data["destination"] = data.destination
    if data.start_date is not None:
        update_data["start_date"] = data.start_date
    if data.end_date is not None:
        update_data["end_date"] = data.end_date
    if data.notes is not None:
        update_data["notes"] = data.notes
    if data.status is not None:
        update_data["status"] = data.status
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await itineraries_col.update_one(
        {"tourist_id": user_id, "id": itinerary_id},
        {"$set": update_data},
    )

    updated = await itineraries_col.find_one({"tourist_id": user_id, "id": itinerary_id})
    return ItineraryResponse(
        id=updated["id"],
        tourist_id=updated["tourist_id"],
        title=updated["title"],
        destination=updated.get("destination"),
        start_date=updated.get("start_date"),
        end_date=updated.get("end_date"),
        notes=updated.get("notes"),
        status=updated.get("status", "active"),
        created_at=updated.get("created_at"),
        updated_at=updated.get("updated_at"),
    )


@router.delete("/me/itinerary/{itinerary_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_itinerary(
    itinerary_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    """Delete an itinerary. Authenticated tourist only."""
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Itinerary deletion required",
        )

    db = get_database()
    itineraries_col = db["itineraries"]

    result = await itineraries_col.delete_one({"tourist_id": user_id, "id": itinerary_id})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Itinerary not found or access denied",
        )