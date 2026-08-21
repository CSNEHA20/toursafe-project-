from fastapi import APIRouter, Depends, HTTPException, status
from ..core.database import get_database
from ..routers.auth import get_current_user
from ..schemas.user import TouristRegister, TouristProfile
from ..models.tourist import Tourist

router = APIRouter(prefix="/api/v1/tourists", tags=["tourists"])


@router.post("/register", response_model=TouristProfile, status_code=status.HTTP_201_CREATED)
async def tourist_register(
    payload: TouristRegister,
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

    tourist = Tourist(
        id=user_id,
        user_id=user_id,
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        nationality=payload.nationality,
        date_of_birth=payload.date_of_birth,
        gender=payload.gender,
        passport_number=payload.passport_number,
        profile_photo_url=payload.profile_photo_url,
        is_active=True,
    )
    await db["tourists"].insert_one(tourist.to_dict())

    return tourist.to_dict()


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

    return tourist.to_response()