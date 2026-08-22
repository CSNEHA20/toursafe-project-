import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from ..models.identity import (
    ConsentType,
    CredentialStatus,
    KYCDocumentType,
    KYCRejectionReason,
    KYCStatus,
    ProviderStatus,
    VerificationResultCode,
)


# ==========================================
# Tourist Identity Profile Schemas
# ==========================================

class TouristIdentityProfileCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    date_of_birth: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    nationality: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=30)
    contact_email: Optional[str] = Field(None, max_length=150)


class TouristIdentityProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=150)
    date_of_birth: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    nationality: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=30)
    contact_email: Optional[str] = Field(None, max_length=150)


class TouristIdentityProfileResponse(BaseModel):
    id: str
    user_id: str
    full_name: str
    date_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    identity_status: KYCStatus
    verified_fields: List[str] = Field(default_factory=list)
    last_verified_at: Optional[datetime] = None
    verification_expires_at: Optional[datetime] = None
    current_credential_id: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"use_enum_values": True, "from_attributes": True}


# ==========================================
# Data Minimization Views (DTOs)
# ==========================================

class TouristSelfIdentityView(BaseModel):
    """View returned to the tourist user themselves."""
    id: str
    user_id: str
    full_name: str
    date_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    identity_status: KYCStatus
    verified_fields: List[str] = Field(default_factory=list)
    last_verified_at: Optional[datetime] = None
    verification_expires_at: Optional[datetime] = None
    current_credential_reference: Optional[str] = None
    active_credential_status: Optional[CredentialStatus] = None
    documents_count: int = 0
    active_consents_count: int = 0

    model_config = {"use_enum_values": True}


class AuthorityTouristIdentityView(BaseModel):
    """View returned to authorized authority operators."""
    identity_profile_id: str
    user_id: str
    full_name: str
    date_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    identity_status: KYCStatus
    verified_fields: List[str] = Field(default_factory=list)
    last_verified_at: Optional[datetime] = None
    verification_expires_at: Optional[datetime] = None
    current_credential_reference: Optional[str] = None
    credential_status: Optional[CredentialStatus] = None
    document_summaries: List[Dict[str, Any]] = Field(default_factory=list)
    verification_history_count: int = 0

    model_config = {"use_enum_values": True}


class ResponderTouristIdentityView(BaseModel):
    """View returned to emergency responders during assigned incident triage."""
    user_id: str
    full_name: str
    nationality: Optional[str] = None
    contact_phone: Optional[str] = None
    identity_verified: bool
    identity_status: KYCStatus
    credential_reference: Optional[str] = None

    model_config = {"use_enum_values": True}


class PublicVerificationResult(BaseModel):
    """
    Public/Authority Verification Endpoint Response.
    Strictly sanitized - NO raw government IDs, addresses, or trip histories.
    """
    credential_reference: str
    result_code: VerificationResultCode
    is_valid: bool
    status: Optional[CredentialStatus] = None
    verified_name: Optional[str] = None
    nationality: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    verification_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    issuer: str = "TourSafe Trust Authority"
    provider_type: str = "DEV_KYC_PROVIDER"

    model_config = {"use_enum_values": True}


# ==========================================
# KYC Document & Workflow Schemas
# ==========================================

class KYCDocumentSubmitRequest(BaseModel):
    document_type: KYCDocumentType
    issuing_country: Optional[str] = Field(None, max_length=100)
    masked_identifier: str = Field(..., min_length=3, max_length=50, description="Masked identifier e.g. '•••• 5678'")
    storage_key: Optional[str] = Field(None, description="Protected secure storage reference")
    file_size_bytes: int = Field(default=1024, ge=0)
    mime_type: str = Field(default="application/pdf")


class KYCReviewAssignRequest(BaseModel):
    reviewer_id: str


class KYCApproveRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=500)
    verified_fields: List[str] = Field(default_factory=lambda: ["full_name", "date_of_birth", "nationality"])
    validity_days: int = Field(default=365, ge=1, le=1825)


class KYCRejectRequest(BaseModel):
    reason: KYCRejectionReason
    details: Optional[str] = Field(None, max_length=500)
    internal_notes: Optional[str] = Field(None, max_length=500)


class KYCRequestActionRequest(BaseModel):
    instructions: str = Field(..., min_length=5, max_length=1000)
    required_document_type: Optional[KYCDocumentType] = None
    internal_notes: Optional[str] = Field(None, max_length=500)


class KYCDocumentResponse(BaseModel):
    id: str
    tourist_id: str
    identity_profile_id: Optional[str] = None
    document_type: KYCDocumentType
    issuing_country: Optional[str] = None
    masked_identifier: str
    file_size_bytes: int
    mime_type: str
    verification_status: KYCStatus
    provider: str
    provider_reference: Optional[str] = None
    rejection_reason: Optional[KYCRejectionReason] = None
    rejection_details: Optional[str] = None
    requires_action_instructions: Optional[str] = None
    reviewer_id: Optional[str] = None
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"use_enum_values": True, "from_attributes": True}


class KYCVerificationHistoryResponse(BaseModel):
    id: str
    identity_profile_id: str
    tourist_id: str
    document_id: Optional[str] = None
    previous_status: str
    new_status: str
    actor_id: str
    actor_role: str
    action: str
    reason: Optional[str] = None
    provider_reference: Optional[str] = None
    timestamp: datetime

    model_config = {"use_enum_values": True, "from_attributes": True}


# ==========================================
# Digital Tourist Credential Schemas
# ==========================================

class CredentialIssueRequest(BaseModel):
    validity_days: int = Field(default=90, ge=1, le=730)


class CredentialRevokeRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=300)


class CredentialSuspendRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=300)


class CredentialVerifyRequest(BaseModel):
    qr_payload: Optional[str] = None
    credential_reference: Optional[str] = None
    verification_context: Optional[str] = Field("authority_checkpoint", max_length=100)


class CredentialResponse(BaseModel):
    id: str
    credential_reference: str
    user_id: str
    identity_profile_id: str
    version: int
    status: CredentialStatus
    issued_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    revocation_reason: Optional[str] = None
    suspended_at: Optional[datetime] = None
    suspension_reason: Optional[str] = None
    replaced_by_credential_id: Optional[str] = None
    signature: str
    token_nonce: str
    qr_payload: str

    model_config = {"use_enum_values": True, "from_attributes": True}


class QRTokenPayload(BaseModel):
    """
    Decoded payload structure for signed QR codes.
    """
    cred_ref: str
    uid: str
    ver: int
    exp: int
    nonce: str
    sig: str


# ==========================================
# Consent & Privacy Schemas
# ==========================================

class ConsentGrantRequest(BaseModel):
    consent_type: ConsentType
    version: str = Field(default="v1.0", max_length=20)
    source: str = Field(default="tourist_app", max_length=50)


class ConsentWithdrawRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=300)


class ConsentResponse(BaseModel):
    id: str
    user_id: str
    consent_type: ConsentType
    version: str
    granted: bool
    source: str
    granted_at: datetime
    withdrawn_at: Optional[datetime] = None
    withdrawal_reason: Optional[str] = None

    model_config = {"use_enum_values": True, "from_attributes": True}


class PrivacyCenterResponse(BaseModel):
    identity_profile: TouristSelfIdentityView
    active_consents: List[ConsentResponse]
    consents_summary: Dict[str, bool]
    data_minimization_notice: str = (
        "TourSafe strictly enforces zero trust/risk scoring. Your raw identity documents are stored in protected storage with metadata masking. Responders receive only emergency-critical information during active incidents."
    )
    real_provider_configured: bool = False
    provider_status: ProviderStatus = ProviderStatus.NOT_CONFIGURED


# ==========================================
# Provider Webhook Schemas
# ==========================================

class ProviderWebhookPayload(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    provider: str
    event_type: str  # "verification.completed", "verification.failed", "verification.requires_action"
    provider_reference: str
    status: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    signature: str
    data: Dict[str, Any] = Field(default_factory=dict)
