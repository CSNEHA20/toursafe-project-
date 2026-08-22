from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from ..core import database as db_core


def get_database():
    return db_core.get_database()
from ..models.identity import KYCDocumentRecord, KYCStatus, KYCVerificationHistory
from ..routers.auth import get_current_user
from ..schemas.identity import (
    AuthorityTouristIdentityView,
    KYCApproveRequest,
    KYCDocumentResponse,
    KYCDocumentSubmitRequest,
    KYCRejectRequest,
    KYCRequestActionRequest,
    KYCReviewAssignRequest,
    KYCVerificationHistoryResponse,
    ProviderWebhookPayload,
)
from ..services.identity.document_storage import document_storage_service
from ..services.identity.identity_service import identity_service
from ..services.identity.kyc_service import kyc_service
from ..services.identity.provider_base import provider_registry

router = APIRouter(tags=["kyc"])


# ==========================================
# Tourist KYC Endpoints
# ==========================================

@router.get("/api/v1/kyc/me")
async def get_my_kyc_state(
    user_id_role: tuple = Depends(get_current_user),
):
    """Get authenticated tourist's KYC status and document summaries."""
    user_id, role = user_id_role
    profile = await kyc_service.get_or_create_identity_profile(user_id)
    db = get_database()

    docs_cursor = db["kyc_documents"].find({"tourist_id": user_id})
    docs = await docs_cursor.to_list(length=10)

    return {
        "identity_profile_id": profile.id,
        "user_id": user_id,
        "identity_status": profile.identity_status,
        "verified_fields": profile.verified_fields,
        "last_verified_at": profile.last_verified_at,
        "verification_expires_at": profile.verification_expires_at,
        "documents": [KYCDocumentResponse.model_validate(d) for d in docs],
    }


@router.post("/api/v1/kyc/start")
async def start_kyc_workflow(
    user_id_role: tuple = Depends(get_current_user),
):
    """Start KYC verification workflow for the tourist."""
    user_id, role = user_id_role
    profile = await kyc_service.start_kyc(user_id)
    return {
        "identity_profile_id": profile.id,
        "user_id": user_id,
        "identity_status": profile.identity_status,
        "message": "KYC verification workflow started. Please submit required document metadata.",
    }


@router.post("/api/v1/kyc/documents", response_model=KYCDocumentResponse, status_code=status.HTTP_201_CREATED)
async def submit_kyc_document(
    payload: KYCDocumentSubmitRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """Submit document metadata for verification. Does not store raw government ID numbers."""
    user_id, role = user_id_role
    doc_record = await kyc_service.submit_document(
        user_id=user_id,
        document_type=payload.document_type,
        masked_identifier=payload.masked_identifier,
        issuing_country=payload.issuing_country,
        storage_key=payload.storage_key,
        file_size_bytes=payload.file_size_bytes,
        mime_type=payload.mime_type,
    )
    return KYCDocumentResponse.model_validate(doc_record.to_dict())


@router.get("/api/v1/kyc/documents", response_model=List[KYCDocumentResponse])
async def list_my_kyc_documents(
    user_id_role: tuple = Depends(get_current_user),
):
    """List all KYC document metadata owned by authenticated tourist."""
    user_id, role = user_id_role
    db = get_database()
    cursor = db["kyc_documents"].find({"tourist_id": user_id})
    docs = await cursor.to_list(length=20)
    return [KYCDocumentResponse.model_validate(d) for d in docs]


@router.get("/api/v1/kyc/documents/{document_id}", response_model=KYCDocumentResponse)
async def get_kyc_document_detail(
    document_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    """Get single document metadata with cross-user access isolation."""
    user_id, role = user_id_role
    db = get_database()
    doc_dict = await db["kyc_documents"].find_one({"id": document_id})
    if not doc_dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KYC document not found")

    # Access control: only owner or authority/admin
    if doc_dict["tourist_id"] != user_id and role not in ("admin", "authority"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to document record")

    return KYCDocumentResponse.model_validate(doc_dict)


@router.delete("/api/v1/kyc/documents/{document_id}")
async def delete_kyc_document(
    document_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    """Delete a pending KYC document."""
    user_id, role = user_id_role
    db = get_database()
    doc_dict = await db["kyc_documents"].find_one({"id": document_id})
    if not doc_dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KYC document not found")

    if doc_dict["tourist_id"] != user_id and role not in ("admin", "authority"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to delete document")

    if doc_dict.get("verification_status") == KYCStatus.VERIFIED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete verified document metadata")

    await db["kyc_documents"].delete_one({"id": document_id})
    return {"message": "Document deleted successfully", "document_id": document_id}


@router.get("/api/v1/kyc/history", response_model=List[KYCVerificationHistoryResponse])
async def get_kyc_history(
    user_id_role: tuple = Depends(get_current_user),
):
    """Get immutable KYC verification history for the authenticated tourist."""
    user_id, role = user_id_role
    db = get_database()
    cursor = db["kyc_verification_history"].find({"tourist_id": user_id}).sort("timestamp", -1)
    history_docs = await cursor.to_list(length=50)
    return [KYCVerificationHistoryResponse.model_validate(h) for h in history_docs]


# ==========================================
# Authority Review Endpoints (RBAC Protected)
# ==========================================

@router.get("/api/v1/authority/kyc/pending")
async def list_pending_kyc_reviews(
    status_filter: Optional[str] = Query(None, description="Filter by status e.g. UNDER_REVIEW, REQUIRES_ACTION"),
    limit: int = Query(50, ge=1, le=100),
    user_id_role: tuple = Depends(get_current_user),
):
    """List pending KYC submissions in the authority review queue."""
    user_id, role = user_id_role
    if not kyc_service.check_permission(role, "KYC_VIEW"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority KYC access required")

    db = get_database()
    query: Dict[str, Any] = {}
    if status_filter:
        query["verification_status"] = status_filter
    else:
        query["verification_status"] = {"$in": [KYCStatus.UNDER_REVIEW, KYCStatus.PENDING, KYCStatus.REQUIRES_ACTION]}

    cursor = db["kyc_documents"].find(query).sort("submitted_at", 1)
    docs = await cursor.to_list(length=limit)
    return {"items": [KYCDocumentResponse.model_validate(d) for d in docs], "count": len(docs)}


@router.get("/api/v1/authority/kyc/{document_id}")
async def get_authority_kyc_detail(
    document_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    """Get full review details for a KYC document including authorized preview token."""
    user_id, role = user_id_role
    if not kyc_service.check_permission(role, "KYC_VIEW"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority KYC access required")

    db = get_database()
    doc_dict = await db["kyc_documents"].find_one({"id": document_id})
    if not doc_dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KYC document not found")

    doc = KYCDocumentRecord.from_dict(doc_dict)
    identity_view = await identity_service.get_authority_view(doc.identity_profile_id or "")

    # Generate tokenized short-lived access preview link
    preview_url = None
    if doc.storage_key:
        preview_url = document_storage_service.generate_tokenized_access_url(
            storage_key=doc.storage_key,
            requester_user_id=user_id,
            validity_seconds=300,
        )

    # Fetch audit history for this identity profile
    hist_cursor = db["kyc_verification_history"].find({"identity_profile_id": doc.identity_profile_id}).sort("timestamp", -1)
    hist_docs = await hist_cursor.to_list(length=20)

    return {
        "document": KYCDocumentResponse.model_validate(doc.to_dict()),
        "identity_profile": identity_view,
        "preview_url": preview_url,
        "history": [KYCVerificationHistoryResponse.model_validate(h) for h in hist_docs],
    }


@router.post("/api/v1/authority/kyc/{document_id}/assign")
async def assign_kyc_reviewer(
    document_id: str,
    payload: KYCReviewAssignRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """Assign an operator to review a KYC document."""
    user_id, role = user_id_role
    try:
        updated = await kyc_service.assign_reviewer(
            document_id=document_id,
            reviewer_id=payload.reviewer_id,
            reviewer_role=role,
        )
        return KYCDocumentResponse.model_validate(updated.to_dict())
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/api/v1/authority/kyc/{document_id}/approve")
async def approve_kyc_submission(
    document_id: str,
    payload: KYCApproveRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """Approve a KYC submission."""
    user_id, role = user_id_role
    try:
        doc, profile = await kyc_service.approve_kyc(
            document_id=document_id,
            reviewer_id=user_id,
            reviewer_role=role,
            notes=payload.notes,
            verified_fields=payload.verified_fields,
            validity_days=payload.validity_days,
        )
        return {
            "status": "APPROVED",
            "document": KYCDocumentResponse.model_validate(doc.to_dict()),
            "identity_profile_id": profile.id,
            "verified_fields": profile.verified_fields,
            "verification_expires_at": profile.verification_expires_at,
        }
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/api/v1/authority/kyc/{document_id}/reject")
async def reject_kyc_submission(
    document_id: str,
    payload: KYCRejectRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """Reject a KYC submission with structured rejection reason."""
    user_id, role = user_id_role
    try:
        doc, profile = await kyc_service.reject_kyc(
            document_id=document_id,
            reviewer_id=user_id,
            reviewer_role=role,
            reason=payload.reason,
            details=payload.details,
            internal_notes=payload.internal_notes,
        )
        return {
            "status": "REJECTED",
            "document": KYCDocumentResponse.model_validate(doc.to_dict()),
            "reason": payload.reason,
        }
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/api/v1/authority/kyc/{document_id}/request-action")
async def request_kyc_action(
    document_id: str,
    payload: KYCRequestActionRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    """Request additional action or document re-submission from the tourist."""
    user_id, role = user_id_role
    try:
        doc, profile = await kyc_service.request_action(
            document_id=document_id,
            reviewer_id=user_id,
            reviewer_role=role,
            instructions=payload.instructions,
            internal_notes=payload.internal_notes,
        )
        return {
            "status": "REQUIRES_ACTION",
            "document": KYCDocumentResponse.model_validate(doc.to_dict()),
            "instructions": payload.instructions,
        }
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ==========================================
# KYC Provider Webhooks
# ==========================================

@router.post("/api/v1/kyc/webhooks/{provider_name}")
async def handle_provider_webhook(
    provider_name: str,
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
):
    """Secure webhook handler for KYC verification provider callbacks."""
    provider = provider_registry.get_provider(provider_name)
    body_bytes = await request.body()

    if x_signature:
        valid_sig = provider.verify_webhook_signature(body_bytes, x_signature)
        if not valid_sig:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    try:
        payload_data = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    event_id = payload_data.get("event_id", "")
    if hasattr(provider, "record_processed_event") and event_id:
        is_new = provider.record_processed_event(event_id)
        if not is_new:
            return {"status": "ALREADY_PROCESSED", "event_id": event_id}

    return {"status": "RECEIVED", "provider": provider_name, "event_id": event_id}
