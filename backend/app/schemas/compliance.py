"""
Pydantic Schemas for TourSafe Compliance, Privacy, Retention, Governance & Regulatory Readiness.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from ..models.compliance import (
    DataCategory,
    DataClassification,
    PolicyStatus,
    ArchiveBehavior,
    DeletionBehavior,
    LegalHoldStatus,
    LegalHoldScopeType,
    PrivacyRequestType,
    PrivacyRequestStatus,
    ConsentPurpose,
    LegalProcessingBasis,
    VendorStatus,
    SecurityReviewStatus,
    ContractStatus,
    AccessReviewStatus,
    AccessReviewScope,
    FrameworkType,
    ControlStatus,
    ControlDomain,
)


# Retention Policies
class RetentionPolicyCreate(BaseModel):
    data_type: DataCategory
    jurisdiction_id: Optional[str] = None
    retention_period_days: int = Field(gt=0, default=90)
    archive_behavior: ArchiveBehavior = ArchiveBehavior.ARCHIVE_ENCRYPTED
    deletion_behavior: DeletionBehavior = DeletionBehavior.HARD_DELETE
    legal_hold_behavior: str = "BLOCK_DELETION"
    description: str = ""
    effective_from: Optional[datetime] = None


class RetentionPolicyUpdate(BaseModel):
    retention_period_days: Optional[int] = Field(default=None, gt=0)
    archive_behavior: Optional[ArchiveBehavior] = None
    deletion_behavior: Optional[DeletionBehavior] = None
    description: Optional[str] = None
    effective_until: Optional[datetime] = None


class RetentionPolicyResponse(BaseModel):
    id: str
    data_type: str
    jurisdiction_id: Optional[str]
    retention_period_days: int
    archive_behavior: str
    deletion_behavior: str
    legal_hold_behavior: str
    version: int
    effective_from: datetime
    effective_until: Optional[datetime]
    status: str
    created_by: str
    approved_by: Optional[str]
    description: str
    created_at: datetime
    updated_at: datetime


# Legal Holds
class LegalHoldCreate(BaseModel):
    title: str
    reason: str
    scope_type: LegalHoldScopeType
    scope_id: str
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    data_categories: List[DataCategory] = Field(default_factory=list)
    review_date: Optional[datetime] = None
    notes: Optional[str] = None


class LegalHoldRelease(BaseModel):
    release_reason: str


class LegalHoldResponse(BaseModel):
    id: str
    title: str
    reason: str
    scope_type: str
    scope_id: str
    date_range_start: Optional[datetime]
    date_range_end: Optional[datetime]
    data_categories: List[str]
    status: str
    placed_by: str
    placed_at: datetime
    review_date: Optional[datetime]
    released_by: Optional[str]
    released_at: Optional[datetime]
    release_reason: Optional[str]
    notes: Optional[str]
    created_at: datetime


# Privacy Requests (DSR)
class PrivacyRequestCreate(BaseModel):
    request_type: PrivacyRequestType
    scope: List[DataCategory] = Field(default_factory=lambda: [DataCategory.IDENTITY, DataCategory.LOCATION])
    notes: Optional[str] = None
    correction_payload: Optional[Dict[str, Any]] = None


class PrivacyRequestVerify(BaseModel):
    verification_code: str = "VERIFIED_SESSION"
    method: str = "SESSION_AUTH"


class PrivacyRequestReview(BaseModel):
    decision: str  # "APPROVE", "REJECT", "PARTIALLY_FULFILL"
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None


class PrivacyRequestResponse(BaseModel):
    id: str
    subject_id: str
    request_type: str
    scope: List[str]
    status: str
    identity_verified: bool
    identity_verification_method: Optional[str]
    identity_verified_at: Optional[datetime]
    created_at: datetime
    deadline_at: datetime
    assigned_to: Optional[str]
    completed_at: Optional[datetime]
    export_token: Optional[str]
    export_token_expires_at: Optional[datetime]
    partial_deletion_details: Optional[Dict[str, Any]]
    correction_payload: Optional[Dict[str, Any]]
    notes: Optional[str]
    rejection_reason: Optional[str]


# Consents
class ConsentGrantRequest(BaseModel):
    purpose: ConsentPurpose
    source: str = "MOBILE_APP"
    jurisdiction_id: Optional[str] = None


class ConsentWithdrawRequest(BaseModel):
    purpose: ConsentPurpose
    reason: Optional[str] = None


class ConsentResponse(BaseModel):
    id: str
    subject_id: str
    purpose: str
    version: str
    status: str
    granted_at: datetime
    withdrawn_at: Optional[datetime]
    source: str
    jurisdiction_id: Optional[str]
    legal_basis: str
    evidence_hash: str


# Vendor Integration
class VendorIntegrationCreate(BaseModel):
    vendor_name: str
    service_name: str
    data_shared: List[str]
    purpose: str
    vendor_jurisdiction: str
    data_residency_region: str
    cross_border_transfer: bool = False
    risk_level: str = "MEDIUM"
    dpa_reference: Optional[str] = None
    sla_reference: Optional[str] = None


class VendorIntegrationUpdate(BaseModel):
    security_review_status: Optional[SecurityReviewStatus] = None
    contract_status: Optional[ContractStatus] = None
    risk_level: Optional[str] = None
    dpa_reference: Optional[str] = None
    sla_reference: Optional[str] = None
    data_residency_region: Optional[str] = None
    cross_border_transfer: Optional[bool] = None


class VendorIntegrationResponse(BaseModel):
    id: str
    vendor_name: str
    service_name: str
    data_shared: List[str]
    purpose: str
    vendor_jurisdiction: str
    data_residency_region: str
    status: str
    security_review_status: str
    contract_status: str
    cross_border_transfer: bool
    risk_level: str
    dpa_reference: Optional[str]
    sla_reference: Optional[str]
    last_reviewed_at: Optional[datetime]
    next_review_date: Optional[datetime]


# Access Reviews
class AccessReviewCreate(BaseModel):
    title: str
    scope: AccessReviewScope
    period_start: datetime
    period_end: datetime


class AccessReviewItemDecision(BaseModel):
    user_id: str
    decision: str  # "APPROVED", "REVOKED", "MODIFIED", "FLAG_INACTIVE"
    notes: Optional[str] = None


class AccessReviewComplete(BaseModel):
    decisions: List[AccessReviewItemDecision]
    findings: Optional[str] = None


class BreakGlassRequest(BaseModel):
    requested_role: str
    justification: str
    target_scope: str
    duration_hours: int = Field(default=2, le=8, ge=1)


class BreakGlassResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    requested_role: str
    justification: str
    target_scope: str
    requested_at: datetime
    expires_at: datetime
    status: str
    approved_by: Optional[str]


# Compliance Controls & Readiness
class FrameworkReadinessReport(BaseModel):
    framework: str
    total_controls: int
    implemented_count: int
    partial_count: int
    not_implemented_count: int
    requires_review_count: int
    readiness_percentage: float
    gaps_count: int
    generated_at: datetime
    disclaimer: str = "Technical readiness assessment only; not legal certification."
    controls_summary: List[Dict[str, Any]]
