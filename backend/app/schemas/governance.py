"""
TourSafe Authority Administration, Policy Configuration & System Governance Schemas.
Provides validation schemas for:
- Organization & Jurisdiction administration
- Authority User & Role assignment with Separation of Duties
- Responder Administrative Status & Capability management
- Safety Zone Versioning, Overlap Detection & Conflict Analysis
- Unified Versioned Configuration (Draft, Validate, Approve, Reject, Activate, Rollback, Diff, Clone)
- Dry-Run Policy and Safety Rule Simulation Sandbox
- Immutable Audit Explorer & Subsystem Health Monitoring
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, EmailStr

from ..models.governance import (
    AdminUserStatus,
    AuditAction,
    ConfigurationLifecycleStatus,
    ConfigurationType,
    JurisdictionStatus,
    OrganizationStatus,
    OrganizationType,
)
from ..schemas.emergency import IncidentSeverity, NotificationChannel, ResponderCapability, ResponderType


# ---------------------------------------------------------------------------
# Organization Schemas
# ---------------------------------------------------------------------------

class OrganizationCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=2, max_length=50)
    type: OrganizationType = OrganizationType.MUNICIPAL_SAFETY
    jurisdiction_ids: List[str] = Field(default_factory=list)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrganizationUpdateRequest(BaseModel):
    name: Optional[str] = None
    type: Optional[OrganizationType] = None
    jurisdiction_ids: Optional[List[str]] = None
    status: Optional[OrganizationStatus] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class OrganizationResponse(BaseModel):
    id: str
    name: str
    code: str
    type: OrganizationType
    jurisdiction_ids: List[str]
    status: OrganizationStatus
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Jurisdiction Schemas
# ---------------------------------------------------------------------------

class JurisdictionBoundaryValidation(BaseModel):
    valid: bool
    geometry_type: str
    coordinates_count: int
    bounding_box: List[float]  # [min_lon, min_lat, max_lon, max_lat]
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class JurisdictionCreateRequest(BaseModel):
    organization_id: str
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=2, max_length=50)
    boundary: Dict[str, Any]  # GeoJSON Polygon or MultiPolygon
    cross_jurisdiction_allowed: bool = False
    auto_dispatch_allowed: bool = True
    overlap_priority: int = Field(default=10, ge=1, le=100)
    configuration: Dict[str, Any] = Field(default_factory=dict)


class JurisdictionUpdateRequest(BaseModel):
    name: Optional[str] = None
    boundary: Optional[Dict[str, Any]] = None
    status: Optional[JurisdictionStatus] = None
    cross_jurisdiction_allowed: Optional[bool] = None
    auto_dispatch_allowed: Optional[bool] = None
    overlap_priority: Optional[int] = None
    configuration: Optional[Dict[str, Any]] = None


class JurisdictionResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    code: str
    boundary: Dict[str, Any]
    center: Optional[Dict[str, Any]] = None
    status: JurisdictionStatus
    cross_jurisdiction_allowed: bool
    auto_dispatch_allowed: bool
    overlap_priority: int
    configuration: Dict[str, Any]
    created_at: str
    updated_at: str


class OverlapAnalysisResult(BaseModel):
    has_overlap: bool
    overlapping_jurisdictions: List[Dict[str, Any]] = Field(default_factory=list)
    overlapping_zones: List[Dict[str, Any]] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Authority User & Role Governance Schemas
# ---------------------------------------------------------------------------

class AuthorityUserAdminCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    role: str = Field(default="authority", description="'authority', 'supervisor', 'authority_admin', 'system_admin'")
    organization_id: Optional[str] = None
    jurisdiction_id: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    status: AdminUserStatus = AdminUserStatus.ACTIVE


class AuthorityUserAdminUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    organization_id: Optional[str] = None
    jurisdiction_id: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[AdminUserStatus] = None


class AuthorityUserAdminResponse(BaseModel):
    user_id: str
    email: str
    full_name: Optional[str] = None
    role: str
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    jurisdiction_id: Optional[str] = None
    jurisdiction_name: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    status: str
    is_active: bool
    last_login_at: Optional[str] = None
    created_at: str


# ---------------------------------------------------------------------------
# Responder Administrative Governance Schemas
# ---------------------------------------------------------------------------

class ResponderAdminStatusUpdate(BaseModel):
    admin_status: str = Field(..., description="'ACTIVE', 'SUSPENDED', 'INACTIVE'")
    reason: str = Field(..., min_length=3, description="Justification for administrative status change")
    preserve_ongoing_assignments: bool = Field(default=True, description="Do not silently terminate active field incidents")


class ResponderAdminUnitUpdate(BaseModel):
    unit_name: str
    jurisdiction_id: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    members: List[str] = Field(default_factory=list)
    status: str = "AVAILABLE"


# ---------------------------------------------------------------------------
# Zone Versioning & Governance Schemas
# ---------------------------------------------------------------------------

class ZoneGovernanceVersionRecord(BaseModel):
    version_id: str
    zone_id: str
    version_number: int
    name: str
    zone_type: str
    risk_level: str
    status: str
    boundary: Dict[str, Any]
    properties: Dict[str, Any]
    created_by: str
    approved_by: Optional[str] = None
    change_reason: str
    created_at: str


class ZoneConflictAnalysisRequest(BaseModel):
    boundary: Dict[str, Any]
    zone_type: str
    zone_id: Optional[str] = None


class ZoneConflictAnalysisResponse(BaseModel):
    has_conflicts: bool
    overlapping_zones: List[Dict[str, Any]]
    conflict_details: List[str]
    recommendations: List[str]


# ---------------------------------------------------------------------------
# Unified Versioned Configuration Lifecycle Schemas
# ---------------------------------------------------------------------------

class ConfigurationCreateDraftRequest(BaseModel):
    type: ConfigurationType
    name: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = ""
    version: str = Field(default="v1.0.0", description="Semantic version string, e.g., v1.0.0, v1.1.0")
    jurisdiction_id: Optional[str] = None
    parameters: Dict[str, Any]
    change_reason: str = Field(..., min_length=3)
    dependencies: List[str] = Field(default_factory=list)


class ConfigurationUpdateDraftRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    change_reason: Optional[str] = None
    dependencies: Optional[List[str]] = None


class ConfigurationValidationResult(BaseModel):
    valid: bool
    configuration_id: str
    type: ConfigurationType
    version: str
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    dependency_checks: List[Dict[str, Any]] = Field(default_factory=list)


class ConfigurationApproveRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="Approval justification and operational sign-off")


class ConfigurationRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=3, description="Reason for rejection")


class ConfigurationActivateRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="Operational activation note")


class ConfigurationRollbackRequest(BaseModel):
    target_version_id: str = Field(..., description="Configuration ID of target approved version to revert to")
    reason: str = Field(..., min_length=3, description="Critical rollback justification")


class ConfigurationDiffResponse(BaseModel):
    source_version: str
    target_version: str
    source_config_id: str
    target_config_id: str
    added_keys: Dict[str, Any]
    removed_keys: Dict[str, Any]
    modified_keys: Dict[str, Dict[str, Any]]  # {key: {"old": v1, "new": v2}}
    summary: str


class ConfigurationRecordResponse(BaseModel):
    configuration_id: str
    type: ConfigurationType
    name: str
    description: str
    version: str
    status: ConfigurationLifecycleStatus
    jurisdiction_id: Optional[str] = None
    parameters: Dict[str, Any]
    change_reason: str
    created_by: str
    approved_by: Optional[str] = None
    rejected_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    activated_by: Optional[str] = None
    retired_by: Optional[str] = None
    previous_version_id: Optional[str] = None
    rollback_target_version_id: Optional[str] = None
    dependencies: List[str]
    validation_results: Dict[str, Any]
    activated_at: Optional[str] = None
    retired_at: Optional[str] = None
    created_at: str
    updated_at: str


class ConfigurationExportResponse(BaseModel):
    export_id: str
    generated_at: str
    system_version: str
    scrubbed_secrets: bool = True
    configurations: List[ConfigurationRecordResponse]


class ConfigurationImportRequest(BaseModel):
    configurations: List[Dict[str, Any]]
    import_as_draft: bool = True  # Always forced to True server-side for safety


# ---------------------------------------------------------------------------
# Policy & Safety Simulation Schemas
# ---------------------------------------------------------------------------

class PolicySimulationContext(BaseModel):
    incident_type: str = "MANUAL_SOS"
    severity: IncidentSeverity = IncidentSeverity.HIGH
    latitude: float = 40.7128
    longitude: float = -74.0060
    zone_id: Optional[str] = None
    available_responders_count: int = 3
    parameters: Dict[str, Any] = Field(default_factory=dict)


class PolicySimulationResponse(BaseModel):
    policy_id: str
    policy_name: str
    version: str
    simulation_timestamp: str
    simulated_stages: List[Dict[str, Any]]
    simulated_dispatches: List[Dict[str, Any]]
    simulated_notifications: List[Dict[str, Any]]
    expected_escalation_path: List[str]
    potential_risks_identified: List[str]


class SafetyRuleSimulationRequest(BaseModel):
    candidate_config_id: Optional[str] = None
    custom_parameters: Optional[Dict[str, Any]] = None
    sample_signals: List[Dict[str, Any]] = Field(default_factory=list)


class SafetyRuleSimulationResponse(BaseModel):
    baseline_version: str
    candidate_version: Optional[str] = None
    composite_risk_score_baseline: float
    composite_risk_score_candidate: float
    baseline_state: str
    candidate_state: str
    domain_breakdown_baseline: Dict[str, float]
    domain_breakdown_candidate: Dict[str, float]
    sensitivity_delta: float
    explainability: List[str]


# ---------------------------------------------------------------------------
# Audit Explorer Schemas
# ---------------------------------------------------------------------------

class AuditQueryFilter(BaseModel):
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None
    action: Optional[AuditAction] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    jurisdiction_id: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=200)


class AuditRecordResponse(BaseModel):
    audit_id: str
    timestamp: str
    actor_id: str
    actor_name: Optional[str] = None
    actor_role: str
    action: str
    resource_type: str
    resource_id: str
    jurisdiction_id: Optional[str] = None
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    change_reason: Optional[str] = None
    ip_address: Optional[str] = None
    integrity_hash: Optional[str] = None


class AuditPaginatedResponse(BaseModel):
    items: List[AuditRecordResponse]
    total: int
    page: int
    limit: int
    pages: int


# ---------------------------------------------------------------------------
# System Governance Overview & Health Schemas
# ---------------------------------------------------------------------------

class SubsystemHealth(BaseModel):
    subsystem: str  # "api", "mongodb", "redis", "realtime", "notifications", "telemetry", "ml_inference", "orchestrator"
    status: str     # "HEALTHY", "DEGRADED", "DOWN", "UNKNOWN"
    latency_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    last_check_at: str


class SystemHealthOverviewResponse(BaseModel):
    system_status: str  # "HEALTHY", "DEGRADED", "DOWN"
    timestamp: str
    subsystems: List[SubsystemHealth]
    maintenance_mode: bool
    active_feature_flags: Dict[str, bool]


class AdminOverviewMetricsResponse(BaseModel):
    active_organizations_count: int
    active_jurisdictions_count: int
    active_responders_count: int
    active_zones_count: int
    active_policies_count: int
    pending_approvals_count: int
    recent_audit_events_count_24h: int
    system_health_status: str
    active_safety_config_version: str
    recent_changes: List[Dict[str, Any]]
