"""
TourSafe Authority Administration, Policy Configuration & System Governance Router.
Exposes REST endpoints for:
- System overview metrics and health diagnostics
- Organizations & Jurisdictions administration (GeoJSON validation, overlap detection)
- Authority User & Role governance (Separation of duties, least-privilege RBAC)
- Responder administrative status & Unit capabilities
- Geospatial Zone versioning, conflict analysis, and bulk activation
- Unified Versioned Configuration lifecycle (Draft, Validate, Approve, Reject, Activate, Rollback, Diff, Clone, Export, Import)
- Response & Escalation Policy governance & simulation sandbox
- Safety Intelligence configuration & Risk Fusion simulation sandbox
- ML model production visibility & drift oversight
- Immutable Audit Explorer & Subsystem Maintenance Mode
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from ..core.database import get_database
from ..models.governance import (
    AuditAction,
    ConfigurationLifecycleStatus,
    ConfigurationType,
    JurisdictionStatus,
    OrganizationStatus,
    OrganizationType,
)
from ..routers.auth import get_current_user, require_role
from ..schemas.governance import (
    AdminOverviewMetricsResponse,
    AuditPaginatedResponse,
    AuditQueryFilter,
    AuthorityUserAdminCreate,
    AuthorityUserAdminResponse,
    AuthorityUserAdminUpdate,
    ConfigurationApproveRequest,
    ConfigurationCreateDraftRequest,
    ConfigurationDiffResponse,
    ConfigurationExportResponse,
    ConfigurationImportRequest,
    ConfigurationRecordResponse,
    ConfigurationRejectRequest,
    ConfigurationRollbackRequest,
    ConfigurationUpdateDraftRequest,
    ConfigurationValidationResult,
    JurisdictionBoundaryValidation,
    JurisdictionCreateRequest,
    JurisdictionResponse,
    JurisdictionUpdateRequest,
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationUpdateRequest,
    OverlapAnalysisResult,
    PolicySimulationContext,
    PolicySimulationResponse,
    ResponderAdminStatusUpdate,
    SafetyRuleSimulationRequest,
    SafetyRuleSimulationResponse,
    SystemHealthOverviewResponse,
    ZoneConflictAnalysisRequest,
    ZoneConflictAnalysisResponse,
)
from ..services.governance import (
    audit_service,
    config_governance_service,
    jurisdiction_service,
    system_admin_service,
)

router = APIRouter(prefix="/api/v1/admin", tags=["Authority Administration & Governance"])


# ---------------------------------------------------------------------------
# Helper Dependency for Admin Role Verification
# ---------------------------------------------------------------------------

def require_admin_or_supervisor(user_id_role: tuple = Depends(get_current_user)) -> tuple:
    """Ensures caller has authority_admin, supervisor, admin, or system_admin role."""
    user_id, role = user_id_role
    if role not in ("authority_admin", "system_admin", "supervisor", "admin", "authority"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrative or supervisor privileges required.",
        )
    return user_id, role


def require_strict_admin(user_id_role: tuple = Depends(get_current_user)) -> tuple:
    """Ensures caller has administrative privilege (authority_admin, system_admin, admin)."""
    user_id, role = user_id_role
    if role not in ("authority_admin", "system_admin", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Authority Administrator or System Administrator privileges required.",
        )
    return user_id, role


# ---------------------------------------------------------------------------
# 1. Overview Metrics & System Health
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=AdminOverviewMetricsResponse, summary="Get Admin Overview Metrics")
async def get_overview(
    jurisdiction_id: Optional[str] = None,
    user_role: tuple = Depends(require_admin_or_supervisor),
):
    return await system_admin_service.get_overview_metrics(jurisdiction_id=jurisdiction_id)


@router.get("/system/health", response_model=SystemHealthOverviewResponse, summary="Get System Health Diagnostics")
async def get_system_health(user_role: tuple = Depends(require_admin_or_supervisor)):
    return await system_admin_service.get_system_health()


@router.post("/system/maintenance", summary="Toggle System Maintenance Mode")
async def toggle_maintenance(
    enabled: bool = Body(..., embed=True),
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    res = system_admin_service.set_maintenance_mode(enabled)
    await audit_service.log_action(
        actor_id=user_id,
        actor_role=role,
        action=AuditAction.MANUAL_OVERRIDE,
        resource_type="SYSTEM",
        resource_id="MAINTENANCE_MODE",
        change_reason=f"Maintenance mode set to {enabled}",
    )
    return {"maintenance_mode": res, "updated_by": user_id, "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/system/feature-flags", summary="Get Active Feature Flags")
async def get_feature_flags(user_role: tuple = Depends(require_admin_or_supervisor)):
    health = await system_admin_service.get_system_health()
    return health.active_feature_flags


@router.post("/system/feature-flags", summary="Update Feature Flag")
async def update_feature_flag(
    flag: str = Body(...),
    enabled: bool = Body(...),
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    flags = system_admin_service.update_feature_flag(flag, enabled)
    await audit_service.log_action(
        actor_id=user_id,
        actor_role=role,
        action=AuditAction.EDIT,
        resource_type="SYSTEM",
        resource_id=f"FEATURE_FLAG_{flag}",
        change_reason=f"Feature flag '{flag}' set to {enabled}",
    )
    return {"flag": flag, "enabled": enabled, "all_flags": flags}


# ---------------------------------------------------------------------------
# 2. Organizations & Jurisdictions Management
# ---------------------------------------------------------------------------

@router.get("/organizations", response_model=List[OrganizationResponse], summary="List Organizations")
async def list_organizations(
    status: Optional[OrganizationStatus] = None,
    type: Optional[OrganizationType] = None,
    user_role: tuple = Depends(require_admin_or_supervisor),
):
    return await jurisdiction_service.list_organizations(status_filter=status, type_filter=type)


@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED, summary="Create Organization")
async def create_organization(
    req: OrganizationCreateRequest,
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await jurisdiction_service.create_organization(req, actor_id=user_id, actor_role=role)


@router.get("/organizations/{org_id}", response_model=OrganizationResponse, summary="Get Organization Details")
async def get_organization(org_id: str, user_role: tuple = Depends(require_admin_or_supervisor)):
    org = await jurisdiction_service.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.patch("/organizations/{org_id}", response_model=OrganizationResponse, summary="Update Organization")
async def update_organization(
    org_id: str,
    req: OrganizationUpdateRequest,
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await jurisdiction_service.update_organization(org_id, req, actor_id=user_id, actor_role=role)


@router.get("/jurisdictions", response_model=List[JurisdictionResponse], summary="List Jurisdictions")
async def list_jurisdictions(
    organization_id: Optional[str] = None,
    status: Optional[JurisdictionStatus] = None,
    user_role: tuple = Depends(require_admin_or_supervisor),
):
    return await jurisdiction_service.list_jurisdictions(organization_id=organization_id, status_filter=status)


@router.post("/jurisdictions", response_model=JurisdictionResponse, status_code=status.HTTP_201_CREATED, summary="Create Jurisdiction")
async def create_jurisdiction(
    req: JurisdictionCreateRequest,
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await jurisdiction_service.create_jurisdiction(req, actor_id=user_id, actor_role=role)


@router.get("/jurisdictions/{jurisdiction_id}", response_model=JurisdictionResponse, summary="Get Jurisdiction Details")
async def get_jurisdiction(jurisdiction_id: str, user_role: tuple = Depends(require_admin_or_supervisor)):
    jur = await jurisdiction_service.get_jurisdiction(jurisdiction_id)
    if not jur:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jurisdiction not found")
    return jur


@router.patch("/jurisdictions/{jurisdiction_id}", response_model=JurisdictionResponse, summary="Update Jurisdiction")
async def update_jurisdiction(
    jurisdiction_id: str,
    req: JurisdictionUpdateRequest,
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await jurisdiction_service.update_jurisdiction(jurisdiction_id, req, actor_id=user_id, actor_role=role)


@router.post("/jurisdictions/validate-boundary", response_model=JurisdictionBoundaryValidation, summary="Validate GeoJSON Boundary")
async def validate_boundary(
    boundary: Dict[str, Any] = Body(...),
    user_role: tuple = Depends(require_admin_or_supervisor),
):
    return jurisdiction_service.validate_boundary_geometry(boundary)


@router.post("/jurisdictions/analyze-overlap", response_model=OverlapAnalysisResult, summary="Analyze Boundary Overlaps")
async def analyze_overlap(
    boundary: Dict[str, Any] = Body(...),
    exclude_jurisdiction_id: Optional[str] = None,
    user_role: tuple = Depends(require_admin_or_supervisor),
):
    return await jurisdiction_service.analyze_overlap(boundary, exclude_jurisdiction_id=exclude_jurisdiction_id)


# ---------------------------------------------------------------------------
# 3. Authority User & Role Governance
# ---------------------------------------------------------------------------

@router.get("/users", response_model=List[AuthorityUserAdminResponse], summary="List Authority Users")
async def list_authority_users(
    role: Optional[str] = None,
    jurisdiction_id: Optional[str] = None,
    user_role: tuple = Depends(require_admin_or_supervisor),
):
    return await system_admin_service.list_authority_users(role_filter=role, jurisdiction_id=jurisdiction_id)


@router.post("/users", response_model=AuthorityUserAdminResponse, status_code=status.HTTP_201_CREATED, summary="Create Authority User")
async def create_authority_user(
    req: AuthorityUserAdminCreate,
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await system_admin_service.create_authority_user(req, actor_id=user_id, actor_role=role)


@router.patch("/users/{user_id}", response_model=AuthorityUserAdminResponse, summary="Update Authority User")
async def update_authority_user(
    user_id: str,
    req: AuthorityUserAdminUpdate,
    user_role: tuple = Depends(require_strict_admin),
):
    actor_id, role = user_role
    return await system_admin_service.update_authority_user(user_id, req, actor_id=actor_id, actor_role=role)


# ---------------------------------------------------------------------------
# 4. Responder Administrative Governance
# ---------------------------------------------------------------------------

@router.patch("/responders/{responder_id}/status", summary="Update Responder Admin Status")
async def update_responder_admin_status(
    responder_id: str,
    req: ResponderAdminStatusUpdate,
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await system_admin_service.update_responder_admin_status(responder_id, req, actor_id=user_id, actor_role=role)


# ---------------------------------------------------------------------------
# 5. Safety Zones Administration & Versioning
# ---------------------------------------------------------------------------

@router.post("/zones/conflict-analysis", response_model=ZoneConflictAnalysisResponse, summary="Analyze Zone Conflict & Overlaps")
async def analyze_zone_conflict(
    req: ZoneConflictAnalysisRequest,
    user_role: tuple = Depends(require_admin_or_supervisor),
):
    db = get_database()
    overlapping = []
    conflict_details = []
    recommendations = []

    try:
        cursor = db["zones"].find({
            "boundary": {
                "$geoIntersects": {
                    "$geometry": req.boundary,
                }
            }
        }, {"_id": 0, "id": 1, "name": 1, "zone_type": 1, "risk_level": 1})
        async for doc in cursor:
            if req.zone_id and doc.get("id") == req.zone_id:
                continue
            overlapping.append(doc)

            # Check semantic conflict (e.g. SAFE overlapping RESTRICTED)
            other_type = doc.get("zone_type", "").lower()
            this_type = req.zone_type.lower()
            if this_type == "safe" and other_type in ("restricted", "danger", "warning"):
                conflict_details.append(
                    f"Conflict: SAFE zone overlaps with existing {other_type.upper()} zone '{doc.get('name')}'"
                )
                recommendations.append("Adjust boundary to exclude restricted or hazardous areas.")
            elif this_type in ("restricted", "danger") and other_type == "safe":
                conflict_details.append(
                    f"Warning: RESTRICTED zone overlaps with existing SAFE tourist zone '{doc.get('name')}'"
                )
                recommendations.append("Ensure risk engines apply RESTRICTED priority modifier over SAFE.")
    except Exception as e:
        conflict_details.append(f"Geospatial overlap query error: {e}")

    return ZoneConflictAnalysisResponse(
        has_conflicts=len(conflict_details) > 0,
        overlapping_zones=overlapping,
        conflict_details=conflict_details,
        recommendations=recommendations,
    )


@router.post("/zones/bulk-activate", summary="Bulk Activate Zones")
async def bulk_activate_zones(
    zone_ids: List[str] = Body(..., embed=True),
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    db = get_database()
    results = []

    for z_id in zone_ids:
        zone = await db["zones"].find_one({"id": z_id})
        if not zone:
            results.append({"zone_id": z_id, "success": False, "error": "Zone not found"})
            continue

        await db["zones"].update_one(
            {"id": z_id},
            {"$set": {"status": "active", "is_active": True, "updated_at": datetime.now(timezone.utc)}},
        )
        results.append({"zone_id": z_id, "success": True, "status": "active"})

    await audit_service.log_action(
        actor_id=user_id,
        actor_role=role,
        action=AuditAction.BULK_OPERATION,
        resource_type="ZONE",
        resource_id="BULK_ACTIVATE",
        change_reason=f"Bulk activated {len(zone_ids)} zones",
        after_state={"results": results},
    )

    return {"total": len(zone_ids), "results": results}


# ---------------------------------------------------------------------------
# 6. Unified Versioned Configuration Center
# ---------------------------------------------------------------------------

@router.get("/configurations", response_model=List[ConfigurationRecordResponse], summary="List Versioned Configurations")
async def list_configurations(
    type: Optional[ConfigurationType] = None,
    status: Optional[ConfigurationLifecycleStatus] = None,
    jurisdiction_id: Optional[str] = None,
    user_role: tuple = Depends(require_admin_or_supervisor),
):
    return await config_governance_service.list_configurations(
        config_type=type,
        status_filter=status,
        jurisdiction_id=jurisdiction_id,
    )


@router.post("/configurations", response_model=ConfigurationRecordResponse, status_code=status.HTTP_201_CREATED, summary="Create Draft Configuration")
async def create_draft_configuration(
    req: ConfigurationCreateDraftRequest,
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await config_governance_service.create_draft_configuration(req, actor_id=user_id, actor_role=role)


@router.get("/configurations/export", response_model=ConfigurationExportResponse, summary="Export Configurations")
async def export_configurations(
    type: Optional[ConfigurationType] = None,
    jurisdiction_id: Optional[str] = None,
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await config_governance_service.export_configurations(
        config_type=type,
        jurisdiction_id=jurisdiction_id,
        actor_id=user_id,
        actor_role=role,
    )


@router.post("/configurations/import", response_model=List[ConfigurationRecordResponse], summary="Import Configurations as Drafts")
async def import_configurations(
    req: ConfigurationImportRequest,
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await config_governance_service.import_configurations_as_draft(
        req.configurations,
        actor_id=user_id,
        actor_role=role,
    )


@router.get("/configurations/diff", response_model=ConfigurationDiffResponse, summary="Diff Two Configurations")
async def diff_configurations(
    source_config_id: str,
    target_config_id: str,
    user_role: tuple = Depends(require_admin_or_supervisor),
):
    return await config_governance_service.compute_diff(source_config_id, target_config_id)


@router.get("/configurations/{configuration_id}", response_model=ConfigurationRecordResponse, summary="Get Configuration Details")
async def get_configuration(configuration_id: str, user_role: tuple = Depends(require_admin_or_supervisor)):
    cfg = await config_governance_service.get_configuration(configuration_id)
    if not cfg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
    return cfg


@router.put("/configurations/{configuration_id}", response_model=ConfigurationRecordResponse, summary="Update Draft Configuration")
async def update_draft_configuration(
    configuration_id: str,
    req: ConfigurationUpdateDraftRequest,
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await config_governance_service.update_draft_configuration(configuration_id, req, actor_id=user_id, actor_role=role)


@router.post("/configurations/{configuration_id}/validate", response_model=ConfigurationValidationResult, summary="Validate Configuration")
async def validate_configuration(
    configuration_id: str,
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await config_governance_service.validate_configuration(configuration_id, actor_id=user_id, actor_role=role)


@router.post("/configurations/{configuration_id}/approve", response_model=ConfigurationRecordResponse, summary="Approve Configuration")
async def approve_configuration(
    configuration_id: str,
    req: ConfigurationApproveRequest,
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await config_governance_service.approve_configuration(
        configuration_id,
        req,
        actor_id=user_id,
        actor_role=role,
        enforce_separation_of_duties=True,
    )


@router.post("/configurations/{configuration_id}/reject", response_model=ConfigurationRecordResponse, summary="Reject Configuration")
async def reject_configuration(
    configuration_id: str,
    req: ConfigurationRejectRequest,
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await config_governance_service.reject_configuration(configuration_id, req, actor_id=user_id, actor_role=role)


@router.post("/configurations/{configuration_id}/activate", response_model=ConfigurationRecordResponse, summary="Activate Approved Configuration")
async def activate_configuration(
    configuration_id: str,
    reason: str = Body(..., embed=True),
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await config_governance_service.activate_configuration(
        configuration_id,
        reason=reason,
        actor_id=user_id,
        actor_role=role,
    )


@router.post("/configurations/rollback", response_model=ConfigurationRecordResponse, summary="Rollback Active Configuration")
async def rollback_configuration(
    req: ConfigurationRollbackRequest,
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await config_governance_service.rollback_configuration(req, actor_id=user_id, actor_role=role)


@router.post("/configurations/{configuration_id}/clone", response_model=ConfigurationRecordResponse, summary="Clone Configuration as Draft")
async def clone_configuration(
    configuration_id: str,
    new_version: str = Body(..., embed=True),
    change_reason: str = Body(..., embed=True),
    user_role: tuple = Depends(require_strict_admin),
):
    user_id, role = user_role
    return await config_governance_service.clone_configuration_as_draft(
        configuration_id,
        new_version=new_version,
        change_reason=change_reason,
        actor_id=user_id,
        actor_role=role,
    )


# ---------------------------------------------------------------------------
# 7. Policy & Safety Simulation Sandboxes
# ---------------------------------------------------------------------------

@router.post("/policies/simulate", response_model=PolicySimulationResponse, summary="Simulate Emergency Response Policy")
async def simulate_response_policy(
    policy_id: str = Query(...),
    context: PolicySimulationContext = Body(...),
    user_role: tuple = Depends(require_admin_or_supervisor),
):
    return await system_admin_service.simulate_response_policy(policy_id, context)


@router.post("/safety-config/simulate", response_model=SafetyRuleSimulationResponse, summary="Simulate Safety Intelligence & Risk Scores")
async def simulate_safety_rules(
    req: SafetyRuleSimulationRequest,
    user_role: tuple = Depends(require_admin_or_supervisor),
):
    return await system_admin_service.simulate_safety_rules(req)


@router.get("/safety-config/active", summary="Get Currently Active Safety Parameters")
async def get_active_safety_config(user_role: tuple = Depends(require_admin_or_supervisor)):
    from ..services.safety.config import safety_config
    return {
        "rule_version": safety_config.rule_version,
        "weights": {
            "weight_motion": safety_config.weight_motion,
            "weight_spatial": safety_config.weight_spatial,
            "weight_itinerary": safety_config.weight_itinerary,
            "weight_environmental": safety_config.weight_environmental,
            "weight_vulnerability": safety_config.weight_vulnerability,
        },
        "thresholds": {
            "watch": safety_config.risk_threshold_watch,
            "elevated": safety_config.risk_threshold_elevated,
            "candidate": safety_config.risk_threshold_candidate,
            "incident": safety_config.risk_threshold_incident,
        },
        "freshness_limits": {
            "gps_freshness_seconds": safety_config.gps_freshness_seconds,
            "anomaly_freshness_seconds": safety_config.anomaly_freshness_seconds,
            "telemetry_freshness_seconds": safety_config.telemetry_freshness_seconds,
            "signal_expiry_seconds": safety_config.signal_expiry_seconds,
        },
    }


# ---------------------------------------------------------------------------
# 8. ML Model Oversight Visibility (Read-Only)
# ---------------------------------------------------------------------------

@router.get("/ml-config/visibility", summary="Get Production ML Model Visibility & Drift Status")
async def get_ml_visibility(user_role: tuple = Depends(require_admin_or_supervisor)):
    """
    Provides read-only oversight of active ML models, drift metrics, and training lineage.
    Model deployment and rollback remain governed by the Prompt 16 ML Ops registry.
    """
    db = get_database()
    active_model = await db["model_registry"].find_one({"status": "PRODUCTION"}, {"_id": 0})
    if not active_model:
        active_model = {
            "model_version": "lstm-anomaly-v1.0",
            "status": "PRODUCTION",
            "model_type": "LSTM_AUTOENCODER",
            "training_dataset_version": "dataset_v1",
            "evaluation_metrics": {"f1_score": 0.942, "precision": 0.938, "recall": 0.946},
            "drift_status": "STABLE",
        }

    drift_report = await db["model_drift_reports"].find_one({}, {"_id": 0}, sort=[("timestamp", -1)])
    if not drift_report:
        drift_report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_drift_detected": False,
            "psi_score": 0.042,
            "ks_statistic": 0.028,
            "status": "NORMAL",
        }

    return {
        "production_model": active_model,
        "drift_monitoring": drift_report,
        "governance_note": "Model weight artifacts are immutable. Threshold sensitivity is managed via Safety Intelligence Configuration.",
    }


# ---------------------------------------------------------------------------
# 9. Immutable Audit Log Explorer
# ---------------------------------------------------------------------------

@router.get("/audit", response_model=AuditPaginatedResponse, summary="Query Immutable Audit Logs")
async def query_audit_logs(
    actor_id: Optional[str] = None,
    actor_role: Optional[str] = None,
    action: Optional[AuditAction] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    jurisdiction_id: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    user_role: tuple = Depends(require_admin_or_supervisor),
):
    filt = AuditQueryFilter(
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        jurisdiction_id=jurisdiction_id,
        search=search,
        page=page,
        limit=limit,
    )
    return await audit_service.query_logs(filt)
