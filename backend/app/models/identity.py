import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from .user import TimeStampedModel


class KYCStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    REQUIRES_ACTION = "REQUIRES_ACTION"


class KYCDocumentType(str, Enum):
    PASSPORT = "PASSPORT"
    NATIONAL_ID = "NATIONAL_ID"
    DRIVING_LICENSE = "DRIVING_LICENSE"
    AADHAAR = "AADHAAR"
    OTHER = "OTHER"


class KYCRejectionReason(str, Enum):
    DOCUMENT_INVALID = "DOCUMENT_INVALID"
    DOCUMENT_EXPIRED = "DOCUMENT_EXPIRED"
    DOCUMENT_UNREADABLE = "DOCUMENT_UNREADABLE"
    INFORMATION_MISMATCH = "INFORMATION_MISMATCH"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    OTHER = "OTHER"


class CredentialStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    SUSPENDED = "SUSPENDED"
    REPLACED = "REPLACED"


class VerificationResultCode(str, Enum):
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    SUSPENDED = "SUSPENDED"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class ConsentType(str, Enum):
    IDENTITY_VERIFICATION = "IDENTITY_VERIFICATION"
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    LOCATION_PROCESSING = "LOCATION_PROCESSING"
    TELEMETRY_PROCESSING = "TELEMETRY_PROCESSING"
    CREDENTIAL_SHARING = "CREDENTIAL_SHARING"


class ProviderStatus(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class TouristIdentityProfile(TimeStampedModel):
    """
    Dedicated tourist identity profile domain model.
    Decoupled from authentication (User) and safety / incident operations.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str  # References User.id
    full_name: str
    date_of_birth: Optional[str] = None  # YYYY-MM-DD
    nationality: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    identity_status: KYCStatus = KYCStatus.NOT_STARTED
    verified_fields: List[str] = Field(default_factory=list)  # e.g. ["full_name", "date_of_birth"]
    last_verified_at: Optional[datetime] = None
    verification_expires_at: Optional[datetime] = None
    current_credential_id: Optional[str] = None
    is_active: bool = True

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}

    @staticmethod
    def from_dict(data: dict) -> "TouristIdentityProfile":
        return TouristIdentityProfile(
            id=data.get("id", str(uuid.uuid4())),
            user_id=data["user_id"],
            full_name=data["full_name"],
            date_of_birth=data.get("date_of_birth"),
            nationality=data.get("nationality"),
            contact_phone=data.get("contact_phone"),
            contact_email=data.get("contact_email"),
            identity_status=data.get("identity_status", KYCStatus.NOT_STARTED),
            verified_fields=data.get("verified_fields", []),
            last_verified_at=data.get("last_verified_at"),
            verification_expires_at=data.get("verification_expires_at"),
            current_credential_id=data.get("current_credential_id"),
            is_active=data.get("is_active", True),
            created_at=data.get("created_at", datetime.now(timezone.utc)),
            updated_at=data.get("updated_at", datetime.now(timezone.utc)),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "full_name": self.full_name,
            "date_of_birth": self.date_of_birth,
            "nationality": self.nationality,
            "contact_phone": self.contact_phone,
            "contact_email": self.contact_email,
            "identity_status": self.identity_status,
            "verified_fields": self.verified_fields,
            "last_verified_at": self.last_verified_at,
            "verification_expires_at": self.verification_expires_at,
            "current_credential_id": self.current_credential_id,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class KYCDocumentRecord(TimeStampedModel):
    """
    Metadata-only document record. Raw government IDs are never stored unmasked.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tourist_id: str  # References User.id or Tourist.id
    identity_profile_id: Optional[str] = None
    document_type: KYCDocumentType
    issuing_country: Optional[str] = None
    masked_identifier: str  # e.g. "•••• 5678" or "X123••••"
    storage_key: Optional[str] = None  # Protected reference in secure private storage
    file_size_bytes: int = 0
    mime_type: str = "application/pdf"
    verification_status: KYCStatus = KYCStatus.PENDING
    provider: str = "DEV_KYC_PROVIDER"
    provider_reference: Optional[str] = None
    rejection_reason: Optional[KYCRejectionReason] = None
    rejection_details: Optional[str] = None
    requires_action_instructions: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewer_notes: Optional[str] = None  # Internal only, never exposed to tourists
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}

    @staticmethod
    def from_dict(data: dict) -> "KYCDocumentRecord":
        return KYCDocumentRecord(
            id=data.get("id", str(uuid.uuid4())),
            tourist_id=data["tourist_id"],
            identity_profile_id=data.get("identity_profile_id"),
            document_type=data.get("document_type", KYCDocumentType.OTHER),
            issuing_country=data.get("issuing_country"),
            masked_identifier=data.get("masked_identifier", "••••"),
            storage_key=data.get("storage_key"),
            file_size_bytes=data.get("file_size_bytes", 0),
            mime_type=data.get("mime_type", "application/pdf"),
            verification_status=data.get("verification_status", KYCStatus.PENDING),
            provider=data.get("provider", "DEV_KYC_PROVIDER"),
            provider_reference=data.get("provider_reference"),
            rejection_reason=data.get("rejection_reason"),
            rejection_details=data.get("rejection_details"),
            requires_action_instructions=data.get("requires_action_instructions"),
            reviewer_id=data.get("reviewer_id"),
            reviewer_notes=data.get("reviewer_notes"),
            submitted_at=data.get("submitted_at", datetime.now(timezone.utc)),
            reviewed_at=data.get("reviewed_at"),
            verified_at=data.get("verified_at"),
            expires_at=data.get("expires_at"),
            created_at=data.get("created_at", datetime.now(timezone.utc)),
            updated_at=data.get("updated_at", datetime.now(timezone.utc)),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tourist_id": self.tourist_id,
            "identity_profile_id": self.identity_profile_id,
            "document_type": self.document_type,
            "issuing_country": self.issuing_country,
            "masked_identifier": self.masked_identifier,
            "storage_key": self.storage_key,
            "file_size_bytes": self.file_size_bytes,
            "mime_type": self.mime_type,
            "verification_status": self.verification_status,
            "provider": self.provider,
            "provider_reference": self.provider_reference,
            "rejection_reason": self.rejection_reason,
            "rejection_details": self.rejection_details,
            "requires_action_instructions": self.requires_action_instructions,
            "reviewer_id": self.reviewer_id,
            "reviewer_notes": self.reviewer_notes,
            "submitted_at": self.submitted_at,
            "reviewed_at": self.reviewed_at,
            "verified_at": self.verified_at,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class KYCVerificationHistory(BaseModel):
    """
    Immutable audit trail record for each KYC transition.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    identity_profile_id: str
    tourist_id: str
    document_id: Optional[str] = None
    previous_status: str
    new_status: str
    actor_id: str
    actor_role: str
    action: str  # e.g. "SUBMIT", "START_REVIEW", "APPROVE", "REJECT", "REQUEST_ACTION", "EXPIRE", "SUSPEND"
    reason: Optional[str] = None
    provider_reference: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"use_enum_values": True, "arbitrary_types_allowed": True}

    @staticmethod
    def from_dict(data: dict) -> "KYCVerificationHistory":
        return KYCVerificationHistory(
            id=data.get("id", str(uuid.uuid4())),
            identity_profile_id=data["identity_profile_id"],
            tourist_id=data["tourist_id"],
            document_id=data.get("document_id"),
            previous_status=data["previous_status"],
            new_status=data["new_status"],
            actor_id=data["actor_id"],
            actor_role=data["actor_role"],
            action=data["action"],
            reason=data.get("reason"),
            provider_reference=data.get("provider_reference"),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", datetime.now(timezone.utc)),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "identity_profile_id": self.identity_profile_id,
            "tourist_id": self.tourist_id,
            "document_id": self.document_id,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "actor_id": self.actor_id,
            "actor_role": self.actor_role,
            "action": self.action,
            "reason": self.reason,
            "provider_reference": self.provider_reference,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class DigitalTouristCredential(TimeStampedModel):
    """
    Digital Tourist Credential issued upon verified identity.
    Contains cryptographic signature and opaque reference.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    credential_reference: str = Field(default_factory=lambda: f"TS-CRED-{uuid.uuid4().hex[:12].upper()}")
    user_id: str
    identity_profile_id: str
    version: int = 1
    status: CredentialStatus = CredentialStatus.ACTIVE
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    revocation_reason: Optional[str] = None
    suspended_at: Optional[datetime] = None
    suspension_reason: Optional[str] = None
    replaced_by_credential_id: Optional[str] = None
    signature: str  # HMAC-SHA256 signature
    token_nonce: str = Field(default_factory=lambda: uuid.uuid4().hex)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}

    @staticmethod
    def from_dict(data: dict) -> "DigitalTouristCredential":
        return DigitalTouristCredential(
            id=data.get("id", str(uuid.uuid4())),
            credential_reference=data.get("credential_reference", f"TS-CRED-{uuid.uuid4().hex[:12].upper()}"),
            user_id=data["user_id"],
            identity_profile_id=data["identity_profile_id"],
            version=data.get("version", 1),
            status=data.get("status", CredentialStatus.ACTIVE),
            issued_at=data.get("issued_at", datetime.now(timezone.utc)),
            expires_at=data["expires_at"],
            revoked_at=data.get("revoked_at"),
            revocation_reason=data.get("revocation_reason"),
            suspended_at=data.get("suspended_at"),
            suspension_reason=data.get("suspension_reason"),
            replaced_by_credential_id=data.get("replaced_by_credential_id"),
            signature=data.get("signature", ""),
            token_nonce=data.get("token_nonce", uuid.uuid4().hex),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", datetime.now(timezone.utc)),
            updated_at=data.get("updated_at", datetime.now(timezone.utc)),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "credential_reference": self.credential_reference,
            "user_id": self.user_id,
            "identity_profile_id": self.identity_profile_id,
            "version": self.version,
            "status": self.status,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "revoked_at": self.revoked_at,
            "revocation_reason": self.revocation_reason,
            "suspended_at": self.suspended_at,
            "suspension_reason": self.suspension_reason,
            "replaced_by_credential_id": self.replaced_by_credential_id,
            "signature": self.signature,
            "token_nonce": self.token_nonce,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ConsentRecord(TimeStampedModel):
    """
    Explicit versioned consent record.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    consent_type: ConsentType
    version: str = "v1.0"
    granted: bool = True
    source: str = "tourist_app"  # e.g. "tourist_app", "web_portal"
    granted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    withdrawn_at: Optional[datetime] = None
    withdrawal_reason: Optional[str] = None
    ip_address: Optional[str] = None

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}

    @staticmethod
    def from_dict(data: dict) -> "ConsentRecord":
        return ConsentRecord(
            id=data.get("id", str(uuid.uuid4())),
            user_id=data["user_id"],
            consent_type=data.get("consent_type", ConsentType.IDENTITY_VERIFICATION),
            version=data.get("version", "v1.0"),
            granted=data.get("granted", True),
            source=data.get("source", "tourist_app"),
            granted_at=data.get("granted_at", datetime.now(timezone.utc)),
            withdrawn_at=data.get("withdrawn_at"),
            withdrawal_reason=data.get("withdrawal_reason"),
            ip_address=data.get("ip_address"),
            created_at=data.get("created_at", datetime.now(timezone.utc)),
            updated_at=data.get("updated_at", datetime.now(timezone.utc)),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "consent_type": self.consent_type,
            "version": self.version,
            "granted": self.granted,
            "source": self.source,
            "granted_at": self.granted_at,
            "withdrawn_at": self.withdrawn_at,
            "withdrawal_reason": self.withdrawal_reason,
            "ip_address": self.ip_address,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class CredentialVerificationLog(BaseModel):
    """
    Immutable audit log entry for credential QR verification queries.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    credential_reference: str
    result_code: VerificationResultCode
    verifier_user_id: Optional[str] = None
    verifier_role: Optional[str] = None  # "authority", "responder", "public"
    request_origin: Optional[str] = None
    client_ip_hash: Optional[str] = None  # Anonymized IP hash
    verification_context: Optional[str] = None  # e.g. "checkpoint", "incident_triage"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"use_enum_values": True, "arbitrary_types_allowed": True}

    @staticmethod
    def from_dict(data: dict) -> "CredentialVerificationLog":
        return CredentialVerificationLog(
            id=data.get("id", str(uuid.uuid4())),
            credential_reference=data["credential_reference"],
            result_code=data.get("result_code", VerificationResultCode.UNKNOWN),
            verifier_user_id=data.get("verifier_user_id"),
            verifier_role=data.get("verifier_role", "public"),
            request_origin=data.get("request_origin"),
            client_ip_hash=data.get("client_ip_hash"),
            verification_context=data.get("verification_context"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc)),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "credential_reference": self.credential_reference,
            "result_code": self.result_code,
            "verifier_user_id": self.verifier_user_id,
            "verifier_role": self.verifier_role,
            "request_origin": self.request_origin,
            "client_ip_hash": self.client_ip_hash,
            "verification_context": self.verification_context,
            "timestamp": self.timestamp,
        }
