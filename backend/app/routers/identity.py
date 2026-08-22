from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..models.identity import ConsentType
from ..routers.auth import get_current_user
from ..schemas.identity import (
    ConsentGrantRequest,
    ConsentResponse,
    ConsentWithdrawRequest,
    PrivacyCenterResponse,
    TouristIdentityProfileResponse,
    TouristIdentityProfileUpdate,
    TouristSelfIdentityView,
)
from ..services.identity.consent_service import consent_service
from ..services.identity.identity_service import identity_service
from ..services.identity.kyc_service import kyc_service

router = APIRouter(prefix="/api/v1/identity", tags=["identity"])


@router.get("/me", response_model=TouristSelfIdentityView)
async def get_my_identity(
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Get authenticated tourist's sanitized identity self-view.
    """
    user_id, role = user_id_role
    return await identity_service.get_self_view(user_id)


@router.patch("/me", response_model=TouristIdentityProfileResponse)
async def update_my_identity(
    updates: TouristIdentityProfileUpdate,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Update tourist identity profile.
    If sensitive verified fields change, re-verification is triggered per policy.
    """
    user_id, role = user_id_role
    profile = await identity_service.update_profile(user_id, updates)
    return profile


@router.get("/status")
async def get_identity_status(
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Get current identity verification status for the authenticated user.
    """
    user_id, role = user_id_role
    profile = await kyc_service.get_or_create_identity_profile(user_id)
    return {
        "user_id": user_id,
        "identity_profile_id": profile.id,
        "identity_status": profile.identity_status,
        "is_verified": (profile.identity_status == "VERIFIED"),
        "verified_fields": profile.verified_fields,
        "last_verified_at": profile.last_verified_at,
        "verification_expires_at": profile.verification_expires_at,
    }


@router.get("/privacy", response_model=PrivacyCenterResponse)
async def get_privacy_center(
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Get comprehensive Privacy & Consent Center data for the authenticated tourist.
    """
    user_id, role = user_id_role
    return await identity_service.get_privacy_center(user_id)


@router.get("/consents", response_model=List[ConsentResponse])
async def list_consents(
    user_id_role: tuple = Depends(get_current_user),
):
    """
    List all consent records for the authenticated user.
    """
    user_id, role = user_id_role
    consents = await consent_service.get_user_consents(user_id)
    return [
        ConsentResponse(
            id=c.id,
            user_id=c.user_id,
            consent_type=c.consent_type,
            version=c.version,
            granted=c.granted,
            source=c.source,
            granted_at=c.granted_at,
            withdrawn_at=c.withdrawn_at,
            withdrawal_reason=c.withdrawal_reason,
        )
        for c in consents
    ]


@router.post("/consents", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def grant_consent(
    payload: ConsentGrantRequest,
    request: Request,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Explicitly grant a versioned consent category.
    """
    user_id, role = user_id_role
    client_ip = request.client.host if request.client else None
    record = await consent_service.grant_consent(
        user_id=user_id,
        consent_type=payload.consent_type,
        version=payload.version,
        source=payload.source,
        ip_address=client_ip,
    )
    return ConsentResponse(
        id=record.id,
        user_id=record.user_id,
        consent_type=record.consent_type,
        version=record.version,
        granted=record.granted,
        source=record.source,
        granted_at=record.granted_at,
        withdrawn_at=record.withdrawn_at,
        withdrawal_reason=record.withdrawal_reason,
    )


@router.post("/consents/{consent_type}/withdraw")
async def withdraw_consent(
    consent_type: ConsentType,
    payload: ConsentWithdrawRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """
    Withdraw a previously granted consent. Explains safety impacts if applicable.
    """
    user_id, role = user_id_role
    return await consent_service.withdraw_consent(
        user_id=user_id,
        consent_type=consent_type,
        reason=payload.reason,
    )
