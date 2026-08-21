from fastapi import APIRouter, Depends, HTTPException, status
from ..core.database import get_database
from ..routers.auth import get_current_user
from ..schemas.kyc_document import KYCDocumentCreate, KYCDocumentUpdate, KYCDocumentResponse, KYCDocumentList
from ..models.kyc_document import KYCDocument
from typing import List

router = APIRouter(prefix="/api/v1/tourists", tags=["tourists-kyc"])


def get_tourist_db(db = Depends(get_database)):
    return db["tourists"]


def get_kyc_db(db = Depends(get_database)):
    return db["kyc_documents"]


@router.post("/me/kyc", response_model=KYCDocumentResponse, status_code=status.HTTP_201_CREATED)
async def submit_kyc(
    data: KYCDocumentCreate,
    user_id_role: tuple = Depends(get_current_user),
):
    """Submit KYC document metadata. Authenticated tourist only."""
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tourists can submit KYC documents",
        )

    # Check if KYC already exists for this tourist
    existing = await get_kyc_db().find_one({"tourist_id": user_id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="KYC document already exists for this tourist",
        )

    kyc = KYCDocument(
        id="",
        tourist_id=user_id,
        document_type=data.document_type,
        document_reference=data.document_reference,
        status="submitted",
        submitted_at=datetime.now(timezone.utc),
    )
    await get_kyc_db().insert_one(kyc.to_dict())

    return KYCDocumentResponse(
        id=kyc.id,
        tourist_id=kyc.tourist_id,
        document_type=kyc.document_type,
        document_reference=kyc.document_reference,
        status=kyc.status,
        submitted_at=kyc.submitted_at,
        verified_at=kyc.verified_at,
        rejection_reason=kyc.rejection_reason,
        created_at=kyc.created_at,
        updated_at=kyc.updated_at,
    )


@router.get("/me/kyc", response_model=KYCDocumentResponse)
async def get_kyc_status(
    user_id_role: tuple = Depends(get_current_user),
):
    """Get KYC status for authenticated tourist."""
    user_id, role = user_id_role
    if role != "tourist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tourist KYC access required",
        )

    kyc = await get_kyc_db().find_one({"tourist_id": user_id})
    if not kyc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC document not found",
        )

    return KYCDocumentResponse(
        id=kyc["id"],
        tourist_id=kyc["tourist_id"],
        document_type=kyc["document_type"],
        document_reference=kyc["document_reference"],
        status=kyc["status"],
        submitted_at=kyc.get("submitted_at"),
        verified_at=kyc.get("verified_at"),
        rejection_reason=kyc.get("rejection_reason"),
        created_at=kyc.get("created_at"),
        updated_at=kyc.get("updated_at"),
    )


@router.patch("/me/kyc", response_model=KYCDocumentResponse)
async def update_kyc_status(
    data: KYCDocumentUpdate,
    user_id_role: tuple = Depends(get_current_user),
):
    """Update KYC status. Only admin can change verification status."""
    user_id, role = user_id_role

    kyc = await get_kyc_db().find_one({"tourist_id": user_id})
    if not kyc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC document not found",
        )

    # Only admin can update verification status
    if role not in ("admin",):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can update KYC verification status",
        )

    update_dict = {"status": data.status, "updated_at": datetime.now(timezone.utc)}
    if data.status == "verified":
        update_dict["verified_at"] = datetime.now(timezone.utc)
    elif data.status == "rejected" and data.rejection_reason:
        update_dict["rejection_reason"] = data.rejection_reason

    await get_kyc_db().update_one(
        {"tourist_id": user_id},
        {"$set": update_dict},
    )

    updated = await get_kyc_db().find_one({"tourist_id": user_id})
    return KYCDocumentResponse(
        id=updated["id"],
        tourist_id=updated["tourist_id"],
        document_type=updated["document_type"],
        document_reference=updated["document_reference"],
        status=updated["status"],
        submitted_at=updated.get("submitted_at"),
        verified_at=updated.get("verified_at"),
        rejection_reason=updated.get("rejection_reason"),
        created_at=updated.get("created_at"),
        updated_at=updated.get("updated_at"),
    )