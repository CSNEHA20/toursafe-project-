from fastapi import APIRouter, Depends, HTTPException, status
from ..core.database import get_database
from ..routers.auth import get_current_user
from ..schemas.user import TouristProfile
from ..models.tourist import Tourist

router = APIRouter(prefix="/api/v1/tourists", tags=["tourists"])


@router.post("/register", response_model=TouristProfile, status_code=status.HTTP_201_CREATED)
async def tourist_register(
    payload: dict,
    user_id_role: tuple = Depends(get_current_user),
):
    """Create a tourist account after user registration.

    This creates the Tourist profile associated with a User account.
    The user_id in the Tourist doc references the User.id.
    """
    user_id, role = user_id_role

    # Only tourists can register tourist profiles
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tourist accounts can create tourist profiles",
        )

    db = get_database()

    # Check if tourist profile already exists for this user
    existing = await db["tourists"].find_one({"user_id": user_id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tourist profile already exists for this user",
        )

    # Build tourist data from payload, supporting new KYC and contact fields
    tourist_data = {
        "id": user_id,
        "user_id": user_id,
        "full_name": payload.get("full_name", ""),
        "email": payload.get("email", ""),
        "phone": payload.get("phone"),
        "nationality": payload.get("nationality"),
        "date_of_birth": payload.get("date_of_birth"),
        "gender": payload.get("gender"),
        "passport_number": payload.get("passport_number"),
        "profile_photo_url": payload.get("profile_photo_url"),
        "address": payload.get("address"),
        "city": payload.get("city"),
        "country": payload.get("country"),
        "kyc_status": payload.get("kyc_status", "pending"),
        "identity_document_type": payload.get("identity_document_type"),
        "identity_document_reference": payload.get("identity_document_reference"),
        "identity_verified_at": payload.get("identity_verified_at"),
        "is_active": True,
    }

    tourist = Tourist(**tourist_data)
    await db["tourists"].insert_one(tourist.to_dict())

    return TouristProfile(**tourist.to_dict()).model_dump() if hasattr(tourist.to_dict(), "model_dump") else tourist.to_dict()


@router.get("/me", response_model=TouristProfile)
async def tourist_me(user_id_role: tuple = Depends(get_current_user)):
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tourist profile access required",
        )

    db = get_database()
    tourist = await db["tourists"].find_one({"user_id": user_id})
    if not tourist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tourist profile not found",
        )

    return TouristProfile(**tourist).model_dump() if hasattr(tourist, "model_dump") else tourist


@router.patch("/me")
async def tourist_update_profile(
    data: dict,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tourist profile update required",
        )

    db = get_database()
    await db["tourists"].update_one(
        {"user_id": user_id},
        {"$set": {k: v for k, v in data.items() if v is not None}},
    )

    tourist = await db["tourists"].find_one({"user_id": user_id})
    if not tourist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tourist profile not found",
        )

    return tourist


@router.get("/me/status")
async def tourist_me_status(user_id_role: tuple = Depends(get_current_user)):
    """Get tourist profile status including KYC and profile completeness."""
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tourist profile status access required",
        )

    db = get_database()
    tourist = await db["tourists"].find_one({"user_id": user_id})
    if not tourist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tourist profile not found",
        )

    kyc_status = tourist.get("kyc_status", "pending")

    # Calculate profile completeness
    profile_fields = ["full_name", "email", "phone", "nationality", "date_of_birth", "gender",
                      "passport_number", "kyc_status", "identity_document_type"]
    filled_fields = sum(1 for f in profile_fields if tourist.get(f))
    completeness = (filled_fields / len(profile_fields)) * 100 if profile_fields else 0

    return {
        "user_id": user_id,
        "role": role,
        "kyc_status": kyc_status,
        "profile_completeness": round(completeness, 1),
        "is_active": tourist.get("is_active", True),
        "identity_verified": tourist.get("identity_verified_at") is not None,
        "fields": {
            "full_name": bool(tourist.get("full_name")),
            "email": bool(tourist.get("email")),
            "phone": bool(tourist.get("phone")),
            "nationality": bool(tourist.get("nationality")),
            "date_of_birth": bool(tourist.get("date_of_birth")),
            "gender": bool(tourist.get("gender")),
            "passport_number": bool(tourist.get("passport_number")),
            "kyc_status": kyc_status,
            "identity_document_type": bool(tourist.get("identity_document_type")),
        }
    }