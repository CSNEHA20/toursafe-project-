"""
TourSafe Authority Administration, Policy Configuration & System Governance Models.
Defines persistent MongoDB schemas for:
- Organizations and Jurisdictions (GeoJSON boundaries, overlap metadata, cross-jurisdiction policy)
- Authority Admin & Role assignment
- Unified Versioned Governance Configuration records
- Immutable, tamper-evident Audit records
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .user import TimeStampedModel


class OrganizationType(str, Enum):
    POLICE = "POLICE"
    TOURISM_BOARD = "TOURISM_BOARD"
    EMS = "EMS"
    MUNICIPAL_SAFETY = "MUNICIPAL_SAFETY"
    NATIONAL_PARK = "NATIONAL_PARK"
    DISASTER_MANAGEMENT = "DISASTER_MANAGEMENT"
    COAST_GUARD = "COAST_GUARD"
    OTHER = "OTHER"


class OrganizationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"


class JurisdictionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class AdminUserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DEACTIVATED = "DEACTIVATED"


class ConfigurationType(str, Enum):
    SAFETY = "SAFETY"
    RESPONSE_POLICY = "RESPONSE_POLICY"
    ESCALATION = "ESCALATION"
    NOTIFICATION = "NOTIFICATION"
    SYSTEM = "SYSTEM"
    ML_THRESHOLDS = "ML_THRESHOLDS"
    GEOFENCE = "GEOFENCE"
    SECURITY = "SECURITY"


class ConfigurationLifecycleStatus(str, Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"
    REJECTED = "REJECTED"


class AuditAction(str, Enum):
    CREATE = "CREATE"
    EDIT = "EDIT"
    VALIDATE = "VALIDATE"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ACTIVATE = "ACTIVATE"
    ROLLBACK = "ROLLBACK"
    RETIRE = "RETIRE"
    SUSPEND = "SUSPEND"
    REACTIVATE = "REACTIVATE"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    BULK_OPERATION = "BULK_OPERATION"
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"


# ---------------------------------------------------------------------------
# Organization Model
# ---------------------------------------------------------------------------

class Organization(TimeStampedModel):
    id: str = Field(default_factory=lambda: f"org_{uuid.uuid4().hex[:10]}")
    name: str
    code: str  # e.g., "NY-POLICE-01"
    type: OrganizationType = OrganizationType.MUNICIPAL_SAFETY
    jurisdiction_ids: List[str] = Field(default_factory=list)
    status: OrganizationStatus = OrganizationStatus.ACTIVE
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "type": self.type if isinstance(self.type, str) else self.type.value,
            "jurisdiction_ids": self.jurisdiction_ids,
            "status": self.status if isinstance(self.status, str) else self.status.value,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "address": self.address,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }


# ---------------------------------------------------------------------------
# Jurisdiction Model
# ---------------------------------------------------------------------------

class Jurisdiction(TimeStampedModel):
    id: str = Field(default_factory=lambda: f"jur_{uuid.uuid4().hex[:10]}")
    organization_id: str
    name: str
    code: str  # Unique code e.g. "JUR-MANHATTAN-CENTRAL"
    boundary: Dict[str, Any]  # RFC 7946 GeoJSON Polygon or MultiPolygon
    center: Optional[Dict[str, Any]] = None  # GeoJSON Point
    status: JurisdictionStatus = JurisdictionStatus.ACTIVE
    cross_jurisdiction_allowed: bool = False
    auto_dispatch_allowed: bool = True
    overlap_priority: int = 10  # Higher number = higher priority during overlaps
    configuration: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "name": self.name,
            "code": self.code,
            "boundary": self.boundary,
            "center": self.center,
            "status": self.status if isinstance(self.status, str) else self.status.value,
            "cross_jurisdiction_allowed": self.cross_jurisdiction_allowed,
            "auto_dispatch_allowed": self.auto_dispatch_allowed,
            "overlap_priority": self.overlap_priority,
            "configuration": self.configuration,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }


# ---------------------------------------------------------------------------
# Governance Configuration Model (Unified Versioning)
# ---------------------------------------------------------------------------

class GovernanceConfigurationRecord(TimeStampedModel):
    """
    Unified version-controlled governance configuration item.
    Tracks draft authoring, schema validation, multi-user approval,
    atomic activation, rollback history, and dependency references.
    """
    configuration_id: str = Field(default_factory=lambda: f"cfg_{uuid.uuid4().hex[:12]}")
    type: ConfigurationType
    name: str
    description: str = ""
    version: str = "v1.0.0"  # Semantic version e.g. v1.0.0, v1.1.0
    status: ConfigurationLifecycleStatus = ConfigurationLifecycleStatus.DRAFT
    jurisdiction_id: Optional[str] = None  # None = Global / System-wide
    parameters: Dict[str, Any] = Field(default_factory=dict)
    change_reason: str = "Initial baseline configuration"
    created_by: str  # user_id
    approved_by: Optional[str] = None  # user_id (Must not equal created_by if separation of duties enforced)
    rejected_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    activated_by: Optional[str] = None
    retired_by: Optional[str] = None
    previous_version_id: Optional[str] = None
    rollback_target_version_id: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)  # Referenced zone_ids, policy_ids, channel_ids
    validation_results: Dict[str, Any] = Field(default_factory=lambda: {"valid": True, "errors": [], "warnings": []})
    activated_at: Optional[datetime] = None
    retired_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "configuration_id": self.configuration_id,
            "type": self.type if isinstance(self.type, str) else self.type.value,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "status": self.status if isinstance(self.status, str) else self.status.value,
            "jurisdiction_id": self.jurisdiction_id,
            "parameters": self.parameters,
            "change_reason": self.change_reason,
            "created_by": self.created_by,
            "approved_by": self.approved_by,
            "rejected_by": self.rejected_by,
            "rejection_reason": self.rejection_reason,
            "activated_by": self.activated_by,
            "retired_by": self.retired_by,
            "previous_version_id": self.previous_version_id,
            "rollback_target_version_id": self.rollback_target_version_id,
            "dependencies": self.dependencies,
            "validation_results": self.validation_results,
            "activated_at": self.activated_at.isoformat() if isinstance(self.activated_at, datetime) else self.activated_at,
            "retired_at": self.retired_at.isoformat() if isinstance(self.retired_at, datetime) else self.retired_at,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }


# ---------------------------------------------------------------------------
# Immutable Audit Record Model
# ---------------------------------------------------------------------------

class ImmutableAuditRecord(BaseModel):
    """
    Append-only, immutable audit record with cryptographic integrity checksum.
    Records all administrative, policy, zone, role, and override decisions.
    """
    audit_id: str = Field(default_factory=lambda: f"aud_{uuid.uuid4().hex[:14]}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor_id: str
    actor_name: Optional[str] = None
    actor_role: str  # "authority_admin", "system_admin", "supervisor", "authority_operator", "system"
    action: AuditAction
    resource_type: str  # "ORGANIZATION", "JURISDICTION", "USER", "RESPONDER", "ZONE", "POLICY", "CONFIG", "SYSTEM"
    resource_id: str
    jurisdiction_id: Optional[str] = None
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    change_reason: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    integrity_hash: Optional[str] = None

    model_config = {"use_enum_values": True, "populate_by_name": True, "arbitrary_types_allowed": True}

    def compute_integrity_hash(self) -> str:
        """Computes a SHA-256 integrity hash over canonical record attributes."""
        payload = {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            "actor_id": self.actor_id,
            "actor_role": self.actor_role,
            "action": str(self.action),
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "jurisdiction_id": self.jurisdiction_id,
            "change_reason": self.change_reason or "",
            "before_state": self.before_state,
            "after_state": self.after_state,
        }
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        if not self.integrity_hash:
            self.integrity_hash = self.compute_integrity_hash()
        return {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "actor_role": self.actor_role,
            "action": self.action if isinstance(self.action, str) else self.action.value,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "jurisdiction_id": self.jurisdiction_id,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "change_reason": self.change_reason,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "integrity_hash": self.integrity_hash,
        }
