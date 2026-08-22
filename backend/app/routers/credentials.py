from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from ..core import database as db_core


def get_database():
    return db_core.get_database()
from ..models.identity import CredentialStatus, DigitalTouristCredential
from ..routers.auth import get_current_user, get_optional_current_user
from ..schemas.identity import (
    CredentialIssueRequest,
    CredentialResponse,
    CredentialRevokeRequest,
    CredentialSuspendRequest,
    CredentialVerifyRequest,
    PublicVerificationResult,
)
from ..services.identity.credential_service import credential_service

router = APIRouter(prefix="/api/v1/credentials", tags=["credentials"])


# ==========================================
# Tourist Credential Endpoints
# ==========================================

@router.get("/me")
async def get_my_credentials(
    user_id_role: tuple = Depends(get_current_user),
):
    """Get active digital credential and credential history for authenticated tourist."""
    user_id, role = user_id_role
    db = get_database()

    cursor = db["digital_tourist_credentials"].find({"user_id": user_id}).sort("created_at", -1)
    creds_raw = await cursor.to_list(length=20)

    active_cred = None
    history = []

    for d in creds_raw:
        c = DigitalTouristCredential.from_dict(d)
        qr_code = credential_service.generate_qr_payload(c)
        resp = CredentialResponse(
            id=c.id,
            credential_reference=c.credential_reference,
            user_id=c.user_id,
            identity_profile_id=c.identity_profile_id,
            version=c.version,
            status=c.status,
            issued_at=c.issued_at,
            expires_at=c.expires_at,
            revoked_at=c.revoked_at,
            revocation_reason=c.revocation_reason,
            suspended_at=c.suspended_at,
            suspension_reason=c.suspension_reason,
            replaced_by_credential_id=c.replaced_by_credential_id,
            signature=c.signature,
            token_nonce=c.token_nonce,
            qr_payload=qr_code,
        )
        if c.status == CredentialStatus.ACTIVE and not active_cred:
            active_cred = resp
        history.append(resp)

    return {
        "active_credential": active_cred,
        "history": history,
    }


@router.post("/me/rotate-qr", response_model=CredentialResponse)
async def rotate_my_qr_token(
    user_id_role: tuple = Depends(get_current_user),
):
    """Rotate nonce for active credential's QR token."""
    user_id, role = user_id_role
    try:
        cred = await credential_service.rotate_qr_token(user_id)
        qr_payload = credential_service.generate_qr_payload(cred)
        return CredentialResponse(
            id=cred.id,
            credential_reference=cred.credential_reference,
            user_id=cred.user_id,
            identity_profile_id=cred.identity_profile_id,
            version=cred.version,
            status=cred.status,
            issued_at=cred.issued_at,
            expires_at=cred.expires_at,
            signature=cred.signature,
            token_nonce=cred.token_nonce,
            qr_payload=qr_payload,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ==========================================
# Authority / Admin Issuance & Lifecycle Endpoints
# ==========================================

@router.post("/issue/{tourist_id}", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def issue_tourist_credential(
    tourist_id: str,
    payload: CredentialIssueRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """Issue a new Digital Tourist Credential. Requires VERIFIED KYC identity."""
    user_id, role = user_id_role
    if role not in ("admin", "authority"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only authorities can issue credentials")

    try:
        cred = await credential_service.issue_credential(
            user_id=tourist_id,
            validity_days=payload.validity_days,
            issued_by_role=role,
            issued_by_id=user_id,
        )
        qr_payload = credential_service.generate_qr_payload(cred)
        return CredentialResponse(
            id=cred.id,
            credential_reference=cred.credential_reference,
            user_id=cred.user_id,
            identity_profile_id=cred.identity_profile_id,
            version=cred.version,
            status=cred.status,
            issued_at=cred.issued_at,
            expires_at=cred.expires_at,
            signature=cred.signature,
            token_nonce=cred.token_nonce,
            qr_payload=qr_payload,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{credential_id}/revoke", response_model=CredentialResponse)
async def revoke_credential(
    credential_id: str,
    payload: CredentialRevokeRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """Administrative revocation of a credential."""
    user_id, role = user_id_role
    try:
        cred = await credential_service.revoke_credential(
            credential_id=credential_id,
            actor_id=user_id,
            actor_role=role,
            reason=payload.reason,
        )
        qr_payload = credential_service.generate_qr_payload(cred)
        return CredentialResponse(
            id=cred.id,
            credential_reference=cred.credential_reference,
            user_id=cred.user_id,
            identity_profile_id=cred.identity_profile_id,
            version=cred.version,
            status=cred.status,
            issued_at=cred.issued_at,
            expires_at=cred.expires_at,
            revoked_at=cred.revoked_at,
            revocation_reason=cred.revocation_reason,
            signature=cred.signature,
            token_nonce=cred.token_nonce,
            qr_payload=qr_payload,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{credential_id}/suspend", response_model=CredentialResponse)
async def suspend_credential(
    credential_id: str,
    payload: CredentialSuspendRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """Administrative temporary suspension of a credential."""
    user_id, role = user_id_role
    try:
        cred = await credential_service.suspend_credential(
            credential_id=credential_id,
            actor_id=user_id,
            actor_role=role,
            reason=payload.reason,
        )
        qr_payload = credential_service.generate_qr_payload(cred)
        return CredentialResponse(
            id=cred.id,
            credential_reference=cred.credential_reference,
            user_id=cred.user_id,
            identity_profile_id=cred.identity_profile_id,
            version=cred.version,
            status=cred.status,
            issued_at=cred.issued_at,
            expires_at=cred.expires_at,
            suspended_at=cred.suspended_at,
            suspension_reason=cred.suspension_reason,
            signature=cred.signature,
            token_nonce=cred.token_nonce,
            qr_payload=qr_payload,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{credential_id}/unsuspend", response_model=CredentialResponse)
async def unsuspend_credential(
    credential_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    """Administrative un-suspension of a credential."""
    user_id, role = user_id_role
    try:
        cred = await credential_service.unsuspend_credential(
            credential_id=credential_id,
            actor_id=user_id,
            actor_role=role,
        )
        qr_payload = credential_service.generate_qr_payload(cred)
        return CredentialResponse(
            id=cred.id,
            credential_reference=cred.credential_reference,
            user_id=cred.user_id,
            identity_profile_id=cred.identity_profile_id,
            version=cred.version,
            status=cred.status,
            issued_at=cred.issued_at,
            expires_at=cred.expires_at,
            signature=cred.signature,
            token_nonce=cred.token_nonce,
            qr_payload=qr_payload,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ==========================================
# Public & Authority Rate-Limited Verification Endpoint
# ==========================================

@router.post("/verify", response_model=PublicVerificationResult)
async def verify_credential_endpoint(
    payload: CredentialVerifyRequest,
    request: Request,
    optional_user: Optional[tuple] = Depends(get_optional_current_user),
):
    """
    Public / Controlled Credential Verification Endpoint.
    Rate-limited, returns sanitized verification outcome without leaking private identity data.
    """
    client_ip = request.client.host if request.client else "unknown"
    verifier_id = optional_user[0] if optional_user else None
    verifier_role = optional_user[1] if optional_user else "public"

    try:
        result = await credential_service.verify_credential(
            qr_payload=payload.qr_payload,
            credential_reference=payload.credential_reference,
            verifier_user_id=verifier_id,
            verifier_role=verifier_role,
            request_origin=request.headers.get("origin") or request.headers.get("user-agent"),
            client_ip=client_ip,
            verification_context=payload.verification_context,
        )
        return PublicVerificationResult.model_validate(result)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
