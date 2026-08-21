from fastapi import APIRouter, Depends, HTTPException, status
from ..core.database import get_database
from ..routers.auth import get_current_user
from ..schemas.user import AuthorityRegister, AuthorityProfile, VerificationUpdate
from ..models.authority import Authority

router = APIRouter(prefix="/authority", tags=["authority"])


@router.post("/register", response_model=AuthorityProfile, status_code=status.HTTP_201_CREATED)
async def authority_register(
    payload: AuthorityRegister,
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
        full_name=payload.full_name,
        organization_name=payload.organization_name,
        designation=payload.designation,
        phone=payload.phone,
        office_phone=payload.office_phone,
        address=payload.address,
        license_number=payload.license_number,
        verification_status="pending",
    )
    await authority.insert(db)

    return authority.to_response()


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


@router.patch("/me/verification")
async def update_verification(
    payload: VerificationUpdate,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("admin",):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can update verification status",
        )

    db = get_database()
    await db["authority"].update_one(
        {"user_id": user_id},
        {"$set": {"verification_status": payload.verification_status}},
    )

    authority = await db["authority"].find_one({"user_id": user_id})
    if not authority:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authority profile not found",
        )

    return {"detail": "Verification status updated", "verification_status": authority["verification_status"]}