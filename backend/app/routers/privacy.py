"""
TourSafe Privacy & Data Subject Rights (DSR) Router.
Provides endpoints for:
- Tourist granular consent inspection, granting, and withdrawal
- Data Subject Requests (DSR: Access, Export, Correction, Deletion, Restriction)
- Identity verification step for privacy requests
- Administrative DSR review, approval, and execution
- Secure, temporary token-authorized personal data export downloads
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from ..routers.auth import get_current_user
from ..models.compliance import (
    ConsentPurpose,
    PrivacyRequestStatus,
    PrivacyRequestType,
)
from ..schemas.compliance import (
    ConsentGrantRequest,
    ConsentResponse,
    ConsentWithdrawRequest,
    PrivacyRequestCreate,
    PrivacyRequestResponse,
    PrivacyRequestReview,
    PrivacyRequestVerify,
)
from ..services.compliance import (
    consent_service,
    privacy_request_service,
)

router = APIRouter(prefix="/api/v1/privacy", tags=["Privacy & Data Rights"])


# ---------------------------------------------------------------------------
# Consent Management
# ---------------------------------------------------------------------------

@router.get("/consents", response_model=List[ConsentResponse])
async def get_my_consents(
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("id")
    records = await consent_service.get_subject_consents(user_id)
    return [ConsentResponse(**r.model_dump()) for r in records]


@router.post("/consents/grant", response_model=ConsentResponse)
async def grant_consent(
    payload: ConsentGrantRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("id")
    record = await consent_service.grant_consent(
        subject_id=user_id,
        purpose=payload.purpose,
        source=payload.source,
        jurisdiction_id=payload.jurisdiction_id,
    )
    return ConsentResponse(**record.model_dump())


@router.post("/consents/withdraw", response_model=ConsentResponse)
async def withdraw_consent(
    payload: ConsentWithdrawRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("id")
    record = await consent_service.withdraw_consent(
        subject_id=user_id,
        purpose=payload.purpose,
        reason=payload.reason,
    )
    if not record:
        raise HTTPException(status_code=404, detail="No active consent found to withdraw")
    return ConsentResponse(**record.model_dump())


# ---------------------------------------------------------------------------
# Privacy Requests (DSR)
# ---------------------------------------------------------------------------

@router.post("/requests", response_model=PrivacyRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_privacy_request(
    payload: PrivacyRequestCreate,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("id")
    req = await privacy_request_service.create_request(
        subject_id=user_id,
        request_type=payload.request_type,
        scope=payload.scope,
        notes=payload.notes,
        correction_payload=payload.correction_payload,
    )
    return PrivacyRequestResponse(**req.model_dump())


@router.get("/requests", response_model=List[PrivacyRequestResponse])
async def list_privacy_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user),
):
    user_role = current_user.get("role")
    user_id = current_user.get("id")

    # If tourist, only see own requests. If admin/authority, can view all.
    subject_filter = user_id if user_role == "tourist" else None

    requests = await privacy_request_service.get_requests(
        subject_id=subject_filter,
        status=status_filter,
    )
    return [PrivacyRequestResponse(**r.model_dump()) for r in requests]


@router.post("/requests/{request_id}/verify", response_model=PrivacyRequestResponse)
async def verify_privacy_request_identity(
    request_id: str,
    payload: PrivacyRequestVerify,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("id")
    req = await privacy_request_service.verify_identity(
        request_id=request_id,
        subject_id=user_id,
        method=payload.method,
    )
    if not req:
        raise HTTPException(status_code=404, detail="Privacy request not found or not owned by user")
    return PrivacyRequestResponse(**req.model_dump())


@router.post("/requests/{request_id}/review", response_model=PrivacyRequestResponse)
async def review_privacy_request(
    request_id: str,
    payload: PrivacyRequestReview,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") not in ("admin", "authority"):
        raise HTTPException(status_code=403, detail="Insufficient privileges to review privacy requests")

    reviewed = await privacy_request_service.review_request(
        request_id=request_id,
        reviewer_id=current_user.get("id", "admin"),
        decision=payload.decision,
        rejection_reason=payload.rejection_reason,
        notes=payload.notes,
    )
    if not reviewed:
        raise HTTPException(status_code=404, detail="Privacy request not found")
    return PrivacyRequestResponse(**reviewed.model_dump())


@router.get("/export/{token}")
async def download_personal_data_export(
    token: str,
):
    payload = await privacy_request_service.get_export_payload(token)
    if not payload:
        raise HTTPException(status_code=404, detail="Export token invalid or expired")
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f"attachment; filename=toursafe_dsr_export.json"},
    )
