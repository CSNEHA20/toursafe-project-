"""
TourSafe Compliance, Governance, Privacy, Retention & Regulatory Readiness Models.
Defines schemas for:
- Data Classification & Purpose Specification
- Versioned Retention Policies & Multi-Jurisdiction Overrides
- Legal Holds & Safe Deletion Controls
- Data Subject Requests (DSR / Privacy Requests: Access, Export, Correction, Deletion)
- Granular Consent Management & Versioning
- Third-Party Vendor & Cross-Border Data Residency Register
- Access Governance, Periodic Reviews & Audited Break-Glass Access
- Compliance Framework Mapping (ISO 27001, SOC 2, GDPR, DPDP, NIST) & Evidence
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .user import TimeStampedModel


class DataCategory(str, Enum):
    IDENTITY = "IDENTITY"
    KYC = "KYC"
    CONTACT = "CONTACT"
    LOCATION = "LOCATION"
    TELEMETRY = "TELEMETRY"
    INCIDENT = "INCIDENT"
    EMERGENCY = "EMERGENCY"
    RESPONDER = "RESPONDER"
    AUTHORITY = "AUTHORITY"
    COMMUNICATION = "COMMUNICATION"
    ANALYTICS = "ANALYTICS"
    AI = "AI"
    ML = "ML"
    AUDIT = "AUDIT"
    SYSTEM = "SYSTEM"


class DataClassification(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    SENSITIVE = "SENSITIVE"
    CRITICAL = "CRITICAL"


class PolicyStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"
    REJECTED = "REJECTED"


class ArchiveBehavior(str, Enum):
    ARCHIVE_ENCRYPTED = "ARCHIVE_ENCRYPTED"
    HARD_DELETE = "HARD_DELETE"
    SOFT_DELETE = "SOFT_DELETE"
    NOOP = "NOOP"


class DeletionBehavior(str, Enum):
    HARD_DELETE = "HARD_DELETE"
    PSEUDONYMIZE_ANONYMIZE = "PSEUDONYMIZE_ANONYMIZE"
    SOFT_DELETE = "SOFT_DELETE"


class LegalHoldStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


class LegalHoldScopeType(str, Enum):
    USER = "USER"
    INCIDENT = "INCIDENT"
    JURISDICTION = "JURISDICTION"
    DATE_RANGE = "DATE_RANGE"
    DATA_TYPE = "DATA_TYPE"


class PrivacyRequestType(str, Enum):
    ACCESS = "ACCESS"
    CORRECTION = "CORRECTION"
    DELETION = "DELETION"
    RESTRICTION = "RESTRICTION"
    EXPORT = "EXPORT"
    OBJECTION = "OBJECTION"


class PrivacyRequestStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    IDENTITY_VERIFICATION = "IDENTITY_VERIFICATION"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PARTIALLY_FULFILLED = "PARTIALLY_FULFILLED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ConsentPurpose(str, Enum):
    LOCATION_TRACKING = "LOCATION_TRACKING"
    TELEMETRY_PROCESSING = "TELEMETRY_PROCESSING"
    KYC_VERIFICATION = "KYC_VERIFICATION"
    EMERGENCY_COMMUNICATION = "EMERGENCY_COMMUNICATION"
    OPTIONAL_ANALYTICS = "OPTIONAL_ANALYTICS"
    OPTIONAL_PERSONALIZATION = "OPTIONAL_PERSONALIZATION"


class LegalProcessingBasis(str, Enum):
    CONSENT = "CONSENT"
    VITAL_INTERESTS_EMERGENCY = "VITAL_INTERESTS_EMERGENCY"
    LEGAL_OBLIGATION = "LEGAL_OBLIGATION"
    LEGITIMATE_SAFETY_INTEREST = "LEGITIMATE_SAFETY_INTEREST"
    CONTRACT_PERFORMANCE = "CONTRACT_PERFORMANCE"


class VendorStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DECOMMISSIONED = "DECOMMISSIONED"


class SecurityReviewStatus(str, Enum):
    NOT_REVIEWED = "NOT_REVIEWED"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ContractStatus(str, Enum):
    DPA_SIGNED = "DPA_SIGNED"
    SLA_ACTIVE = "SLA_ACTIVE"
    PENDING_RENEWAL = "PENDING_RENEWAL"
    NO_CONTRACT = "NO_CONTRACT"


class AccessReviewStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    OVERDUE = "OVERDUE"


class AccessReviewScope(str, Enum):
    ADMIN_USERS = "ADMIN_USERS"
    AUTHORITY_OFFICERS = "AUTHORITY_OFFICERS"
    RESPONDERS = "RESPONDERS"
    SERVICE_ACCOUNTS = "SERVICE_ACCOUNTS"


class FrameworkType(str, Enum):
    ISO_27001 = "ISO_27001"
    SOC_2 = "SOC_2"
    GDPR_READINESS = "GDPR_READINESS"
    DPDP_READINESS = "DPDP_READINESS"
    NIST_CSF = "NIST_CSF"


class ControlStatus(str, Enum):
    IMPLEMENTED = "IMPLEMENTED"
    PARTIAL = "PARTIAL"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ControlDomain(str, Enum):
    DATA_PROTECTION = "DATA_PROTECTION"
    ACCESS_CONTROL = "ACCESS_CONTROL"
    INCIDENT_RESPONSE = "INCIDENT_RESPONSE"
    AI_ML_GOVERNANCE = "AI_ML_GOVERNANCE"
    AUDIT_LOGGING = "AUDIT_LOGGING"
    INFRASTRUCTURE_SECURITY = "INFRASTRUCTURE_SECURITY"
    THIRD_PARTY_RISK = "THIRD_PARTY_RISK"
    DISASTER_RECOVERY = "DISASTER_RECOVERY"


# ---------------------------------------------------------------------------
# Retention Policy Model
# ---------------------------------------------------------------------------

class RetentionPolicy(TimeStampedModel):
    id: str = Field(default_factory=lambda: f"ret_pol_{uuid.uuid4().hex[:10]}")
    data_type: DataCategory
    jurisdiction_id: Optional[str] = None  # None indicates global baseline policy
    retention_period_days: int = 90
    archive_behavior: ArchiveBehavior = ArchiveBehavior.ARCHIVE_ENCRYPTED
    deletion_behavior: DeletionBehavior = DeletionBehavior.HARD_DELETE
    legal_hold_behavior: str = "BLOCK_DELETION"
    version: int = 1
    effective_from: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    effective_until: Optional[datetime] = None
    status: PolicyStatus = PolicyStatus.ACTIVE
    created_by: str = "system"
    approved_by: Optional[str] = None
    description: str = ""

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Legal Hold Model
# ---------------------------------------------------------------------------

class LegalHold(TimeStampedModel):
    id: str = Field(default_factory=lambda: f"hold_{uuid.uuid4().hex[:10]}")
    title: str
    reason: str
    scope_type: LegalHoldScopeType
    scope_id: str  # user_id, incident_id, or jurisdiction_id
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    data_categories: List[DataCategory] = Field(default_factory=list)
    status: LegalHoldStatus = LegalHoldStatus.ACTIVE
    placed_by: str
    placed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    review_date: Optional[datetime] = None
    released_by: Optional[str] = None
    released_at: Optional[datetime] = None
    release_reason: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Privacy Request (Data Subject Request / DSR) Model
# ---------------------------------------------------------------------------

class PrivacyRequest(TimeStampedModel):
    id: str = Field(default_factory=lambda: f"dsr_{uuid.uuid4().hex[:10]}")
    subject_id: str  # User.id
    request_type: PrivacyRequestType
    scope: List[DataCategory] = Field(default_factory=lambda: [DataCategory.IDENTITY, DataCategory.LOCATION])
    status: PrivacyRequestStatus = PrivacyRequestStatus.SUBMITTED
    identity_verified: bool = False
    identity_verification_method: Optional[str] = None
    identity_verified_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deadline_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assigned_to: Optional[str] = None
    completed_at: Optional[datetime] = None
    export_token: Optional[str] = None
    export_token_expires_at: Optional[datetime] = None
    partial_deletion_details: Optional[Dict[str, Any]] = None
    correction_payload: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Consent Record Model
# ---------------------------------------------------------------------------

class ConsentRecord(TimeStampedModel):
    id: str = Field(default_factory=lambda: f"cns_{uuid.uuid4().hex[:10]}")
    subject_id: str
    purpose: ConsentPurpose
    version: str = "1.0"
    status: str = "GRANTED"  # "GRANTED", "WITHDRAWN", "SUPERSEDED"
    granted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    withdrawn_at: Optional[datetime] = None
    source: str = "MOBILE_APP"  # "MOBILE_APP", "WEB_PORTAL", "KIOSK"
    jurisdiction_id: Optional[str] = None
    legal_basis: LegalProcessingBasis = LegalProcessingBasis.CONSENT
    evidence_hash: str = ""

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Third-Party Vendor Integration Model
# ---------------------------------------------------------------------------

class VendorIntegration(TimeStampedModel):
    id: str = Field(default_factory=lambda: f"vnd_{uuid.uuid4().hex[:10]}")
    vendor_name: str
    service_name: str
    data_shared: List[str] = Field(default_factory=list)
    purpose: str
    vendor_jurisdiction: str
    data_residency_region: str
    status: VendorStatus = VendorStatus.ACTIVE
    security_review_status: SecurityReviewStatus = SecurityReviewStatus.NOT_REVIEWED
    contract_status: ContractStatus = ContractStatus.DPA_SIGNED
    cross_border_transfer: bool = False
    risk_level: str = "MEDIUM"
    dpa_reference: Optional[str] = None
    sla_reference: Optional[str] = None
    last_reviewed_at: Optional[datetime] = None
    next_review_date: Optional[datetime] = None

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Access Review & Break-Glass Models
# ---------------------------------------------------------------------------

class AccessReview(TimeStampedModel):
    id: str = Field(default_factory=lambda: f"arv_{uuid.uuid4().hex[:10]}")
    title: str
    scope: AccessReviewScope
    reviewer_id: str
    period_start: datetime
    period_end: datetime
    status: AccessReviewStatus = AccessReviewStatus.SCHEDULED
    accounts_reviewed: List[Dict[str, Any]] = Field(default_factory=list)
    findings: Optional[str] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}


class BreakGlassSession(TimeStampedModel):
    id: str = Field(default_factory=lambda: f"bg_{uuid.uuid4().hex[:10]}")
    user_id: str
    user_email: str
    requested_role: str
    justification: str
    target_scope: str
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    status: str = "ACTIVE"  # "ACTIVE", "EXPIRED", "REVOKED"
    approved_by: Optional[str] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Compliance Controls & Evidence Models
# ---------------------------------------------------------------------------

class ComplianceControl(TimeStampedModel):
    control_id: str
    framework: FrameworkType
    domain: ControlDomain
    title: str
    description: str
    implementation_status: ControlStatus = ControlStatus.IMPLEMENTED
    evidence_refs: List[str] = Field(default_factory=list)
    owner: str = "security_team"
    review_frequency_days: int = 90
    last_review: Optional[datetime] = None
    next_review: Optional[datetime] = None

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}


class ComplianceEvidence(TimeStampedModel):
    id: str = Field(default_factory=lambda: f"evid_{uuid.uuid4().hex[:10]}")
    control_id: str
    title: str
    artifact_type: str  # "CODE_MODULE", "CONFIG", "POLICY", "AUDIT_RECORD", "TEST_SUITE"
    artifact_location: str
    owner: str
    status: str = "VERIFIED"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}


class ComplianceGap(TimeStampedModel):
    id: str = Field(default_factory=lambda: f"gap_{uuid.uuid4().hex[:10]}")
    framework: FrameworkType
    requirement: str
    current_state: str
    target_state: str
    severity: str = "MEDIUM"
    owner: str = "compliance_lead"
    status: str = "OPEN"  # "OPEN", "IN_PROGRESS", "REQUIRES_LEGAL_REVIEW", "REQUIRES_AUTHORITY_POLICY", "RESOLVED"

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}


class DataDisclosureLog(TimeStampedModel):
    id: str = Field(default_factory=lambda: f"dsc_{uuid.uuid4().hex[:10]}")
    request_type: str  # "LAW_ENFORCEMENT", "REGULATORY_ORDER", "EMERGENCY_SAFETY", "TOURIST_DSR"
    requesting_entity: str
    legal_basis: str
    jurisdiction: str
    data_categories_disclosed: List[str]
    authorized_by: str
    disclosed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expiry_date: Optional[datetime] = None
    notes: Optional[str] = None

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}
