from fastapi import APIRouter, Depends, HTTPException, status
from ..core.database import get_database
from ..routers.auth import get_current_user
from ..schemas.user import AuthorityProfile, VerificationUpdate
from ..models.authority import Authority

router = APIRouter(prefix="/api/v1/authority", tags=["authority"])


def get_authority_db(db = Depends(get_database)):
    return db["authority"]


@router.post("/register", response_model=AuthorityProfile, status_code=status.HTTP_201_CREATED)
async def authority_register(
    payload: dict,
    user_id_role: tuple = Depends(get_current_user),
):
    """Create an authority profile associated with a User account."""
    user_id, role = user_id_role

    # Only authorities/admins can register authority profiles
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authority/admin/responder accounts can create authority profiles",
        )

    db = get_database()

    # Check if authority profile already exists for this user
    existing = await db["authority"].find_one({"user_id": user_id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Authority profile already exists for this user",
        )

    authority = Authority(
        id=user_id,
        user_id=user_id,
        full_name=payload.get("full_name", ""),
        organization_name=payload.get("organization_name"),
        designation=payload.get("designation"),
        phone=payload.get("phone"),
        office_phone=payload.get("office_phone"),
        address=payload.get("address"),
        license_number=payload.get("license_number"),
        verification_status="pending",
    )
    await db["authority"].insert_one(authority.to_dict())

    return AuthorityProfile(**authority.to_dict()).model_dump() if hasattr(authority.to_dict(), "model_dump") else authority.to_dict()


@router.get("/me", response_model=AuthorityProfile)
async def authority_me(user_id_role: tuple = Depends(get_current_user)):
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority profile access required",
        )

    db = get_database()
    authority = await db["authority"].find_one({"user_id": user_id})
    if not authority:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authority profile not found",
        )

    return AuthorityProfile(**authority).model_dump() if hasattr(authority, "model_dump") else authority


@router.patch("/me")
async def authority_update_profile(
    data: dict,
    user_id_role: tuple = Depends(get_current_user),
):
    """Update authority profile. Non-admin users cannot modify verification_status, license_number, or organization_name."""
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority profile update required",
        )

    db = get_database()

    # Filter out administrative fields for non-admin users
    # Only admin can modify verification_status, license_number, organization_name
    filtered_data = {}
    admin_fields = {"verification_status", "license_number", "organization_name"}

    if role == "admin":
        # Admin can modify all fields
        filtered_data = {k: v for k, v in data.items() if v is not None}
    else:
        # Authority/responder can modify personal info only
        for k, v in data.items():
            if v is not None and k not in admin_fields:
                filtered_data[k] = v

    await db["authority"].update_one(
        {"user_id": user_id},
        {"$set": filtered_data},
    )

    authority = await db["authority"].find_one({"user_id": user_id})
    if not authority:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authority profile not found",
        )

    return AuthorityProfile(**authority).model_dump() if hasattr(authority, "model_dump") else authority


@router.get("/me/status")
async def authority_me_status(user_id_role: tuple = Depends(get_current_user)):
    """Get authority profile status. Verification status is read-only for authorities."""
    user_id, role = user_id_role
    if role not in ("authority", "admin", "responder"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority profile status access required",
        )

    db = get_database()
    authority = await db["authority"].find_one({"user_id": user_id})
    if not authority:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authority profile not found",
        )

    return {
        "user_id": user_id,
        "role": role,
        "verification_status": authority.get("verification_status", "pending"),
        "license_number": authority.get("license_number"),
        "organization_name": authority.get("organization_name"),
        "is_modifiable_by_authority": role == "admin",
    }