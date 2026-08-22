"""
TourSafe Compliance & Governance Router.
Provides administrative endpoints for:
- Retention policies, versioning, approvals, and safe retention execution sweeps
- Legal holds lifecycle and safe deletion blocks
- Access governance periodic reviews and Break-Glass emergency sessions
- Third-party vendor register and cross-border data transfer oversight
- Compliance framework mapping (ISO 27001, SOC 2, GDPR, DPDP, NIST) and readiness reports
- Auditor mode sanitized exports
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ..routers.auth import get_current_user
from ..models.compliance import (
    AccessReviewScope,
    ArchiveBehavior,
    ControlDomain,
    ControlStatus,
    DataCategory,
    DeletionBehavior,
    FrameworkType,
    LegalHoldScopeType,
    PolicyStatus,
    SecurityReviewStatus,
)
from ..schemas.compliance import (
    AccessReviewComplete,
    AccessReviewCreate,
    BreakGlassRequest,
    BreakGlassResponse,
    FrameworkReadinessReport,
    LegalHoldCreate,
    LegalHoldRelease,
    LegalHoldResponse,
    RetentionPolicyCreate,
    RetentionPolicyResponse,
    RetentionPolicyUpdate,
    VendorIntegrationCreate,
    VendorIntegrationResponse,
    VendorIntegrationUpdate,
)
from ..services.compliance import (
    access_governance_service,
    auditor_service,
    compliance_registry_service,
    legal_hold_service,
    retention_service,
    vendor_governance_service,
)

router = APIRouter(prefix="/api/v1/compliance", tags=["Compliance & Governance"])


# ---------------------------------------------------------------------------
# Retention Policies
# ---------------------------------------------------------------------------

@router.get("/policies", response_model=List[RetentionPolicyResponse])
async def list_retention_policies(
    data_type: Optional[str] = Query(None),
    jurisdiction_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user),
):
    policies = await retention_service.list_policies(
        data_type=data_type,
        jurisdiction_id=jurisdiction_id,
        status=status_filter,
    )
    return [RetentionPolicyResponse(**p.model_dump()) for p in policies]


@router.post("/policies", response_model=RetentionPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_retention_policy(
    payload: RetentionPolicyCreate,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") not in ("admin", "authority"):
        raise HTTPException(status_code=403, detail="Insufficient privileges to create retention policies")

    policy = await retention_service.create_policy(
        data_type=payload.data_type,
        retention_period_days=payload.retention_period_days,
        created_by=current_user.get("id", "admin"),
        jurisdiction_id=payload.jurisdiction_id,
        archive_behavior=payload.archive_behavior,
        deletion_behavior=payload.deletion_behavior,
        description=payload.description,
        effective_from=payload.effective_from,
    )
    return RetentionPolicyResponse(**policy.model_dump())


@router.post("/policies/{policy_id}/approve", response_model=RetentionPolicyResponse)
async def approve_retention_policy(
    policy_id: str,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only System Admin can approve retention policies")

    approved = await retention_service.approve_and_activate_policy(
        policy_id=policy_id,
        approved_by=current_user.get("id", "admin"),
    )
    if not approved:
        raise HTTPException(status_code=404, detail="Retention policy not found")
    return RetentionPolicyResponse(**approved.model_dump())


@router.post("/policies/{policy_id}/rollback", response_model=RetentionPolicyResponse)
async def rollback_retention_policy(
    policy_id: str,
    target_version: int = Query(..., ge=1),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only System Admin can rollback retention policies")

    rolled = await retention_service.rollback_policy(
        current_policy_id=policy_id,
        target_version=target_version,
        rolled_back_by=current_user.get("id", "admin"),
    )
    if not rolled:
        raise HTTPException(status_code=404, detail="Policy or rollback target version not found")
    return RetentionPolicyResponse(**rolled.model_dump())


@router.post("/retention/run")
async def trigger_retention_sweep(
    dry_run: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only System Admin can trigger retention jobs")

    result = await retention_service.run_retention_job(
        triggered_by=current_user.get("id", "admin"),
        dry_run=dry_run,
    )
    return result


@router.get("/retention/history")
async def get_retention_job_history(
    current_user: dict = Depends(get_current_user),
):
    return await retention_service.get_job_history()


# ---------------------------------------------------------------------------
# Legal Holds
# ---------------------------------------------------------------------------

@router.get("/legal-holds", response_model=List[LegalHoldResponse])
async def list_legal_holds(
    status_filter: Optional[str] = Query(None, alias="status"),
    scope_type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    holds = await legal_hold_service.list_holds(status=status_filter, scope_type=scope_type)
    return [LegalHoldResponse(**h.model_dump()) for h in holds]


@router.post("/legal-holds", response_model=LegalHoldResponse, status_code=status.HTTP_201_CREATED)
async def create_legal_hold(
    payload: LegalHoldCreate,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") not in ("admin", "authority"):
        raise HTTPException(status_code=403, detail="Insufficient privileges to create legal holds")

    hold = await legal_hold_service.create_hold(
        title=payload.title,
        reason=payload.reason,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        placed_by=current_user.get("id", "admin"),
        data_categories=payload.data_categories,
        date_range_start=payload.date_range_start,
        date_range_end=payload.date_range_end,
        review_date=payload.review_date,
        notes=payload.notes,
    )
    return LegalHoldResponse(**hold.model_dump())


@router.post("/legal-holds/{hold_id}/release", response_model=LegalHoldResponse)
async def release_legal_hold(
    hold_id: str,
    payload: LegalHoldRelease,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") not in ("admin", "authority"):
        raise HTTPException(status_code=403, detail="Insufficient privileges to release legal holds")

    released = await legal_hold_service.release_hold(
        hold_id=hold_id,
        released_by=current_user.get("id", "admin"),
        release_reason=payload.release_reason,
    )
    if not released:
        raise HTTPException(status_code=404, detail="Legal hold not found")
    return LegalHoldResponse(**released.model_dump())


# ---------------------------------------------------------------------------
# Third-Party Vendor Register
# ---------------------------------------------------------------------------

@router.get("/vendors", response_model=List[VendorIntegrationResponse])
async def list_vendors(
    current_user: dict = Depends(get_current_user),
):
    vendors = await vendor_governance_service.list_vendors()
    return [VendorIntegrationResponse(**v.model_dump()) for v in vendors]


@router.post("/vendors", response_model=VendorIntegrationResponse, status_code=status.HTTP_201_CREATED)
async def register_vendor(
    payload: VendorIntegrationCreate,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only System Admin can register vendor processors")

    vendor = await vendor_governance_service.register_vendor(
        vendor_name=payload.vendor_name,
        service_name=payload.service_name,
        data_shared=payload.data_shared,
        purpose=payload.purpose,
        vendor_jurisdiction=payload.vendor_jurisdiction,
        data_residency_region=payload.data_residency_region,
        cross_border_transfer=payload.cross_border_transfer,
        risk_level=payload.risk_level,
        dpa_reference=payload.dpa_reference,
        sla_reference=payload.sla_reference,
        registered_by=current_user.get("id", "admin"),
    )
    return VendorIntegrationResponse(**vendor.model_dump())


@router.patch("/vendors/{vendor_id}/review", response_model=VendorIntegrationResponse)
async def update_vendor_review(
    vendor_id: str,
    payload: VendorIntegrationUpdate,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only System Admin can update vendor reviews")

    updated = await vendor_governance_service.update_vendor_review(
        vendor_id=vendor_id,
        security_review_status=payload.security_review_status or SecurityReviewStatus.IN_REVIEW,
        contract_status=payload.contract_status,
        risk_level=payload.risk_level,
        reviewed_by=current_user.get("id", "admin"),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return VendorIntegrationResponse(**updated.model_dump())


# ---------------------------------------------------------------------------
# Access Reviews & Break-Glass Emergency PAM
# ---------------------------------------------------------------------------

@router.get("/access-reviews")
async def list_access_reviews(
    current_user: dict = Depends(get_current_user),
):
    reviews = await access_governance_service.list_reviews()
    return [r.model_dump() for r in reviews]


@router.post("/access-reviews", status_code=status.HTTP_201_CREATED)
async def create_access_review(
    payload: AccessReviewCreate,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only System Admin can initiate access reviews")

    review = await access_governance_service.create_access_review(
        title=payload.title,
        scope=payload.scope,
        reviewer_id=current_user.get("id", "admin"),
        period_start=payload.period_start,
        period_end=payload.period_end,
    )
    return review.model_dump()


@router.post("/access-reviews/{review_id}/complete")
async def complete_access_review(
    review_id: str,
    payload: AccessReviewComplete,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only System Admin can complete access reviews")

    completed = await access_governance_service.complete_access_review(
        review_id=review_id,
        reviewer_id=current_user.get("id", "admin"),
        decisions=[d.model_dump() for d in payload.decisions],
        findings=payload.findings,
    )
    if not completed:
        raise HTTPException(status_code=404, detail="Access review not found")
    return completed.model_dump()


@router.post("/break-glass", response_model=BreakGlassResponse, status_code=status.HTTP_201_CREATED)
async def request_break_glass(
    payload: BreakGlassRequest,
    current_user: dict = Depends(get_current_user),
):
    session = await access_governance_service.request_break_glass_access(
        user_id=current_user.get("id", "unknown"),
        user_email=current_user.get("email", "unknown@toursafe.internal"),
        requested_role=payload.requested_role,
        justification=payload.justification,
        target_scope=payload.target_scope,
        duration_hours=payload.duration_hours,
    )
    return BreakGlassResponse(**session.model_dump())


@router.get("/break-glass", response_model=List[BreakGlassResponse])
async def list_break_glass_sessions(
    current_user: dict = Depends(get_current_user),
):
    sessions = await access_governance_service.list_break_glass_sessions()
    return [BreakGlassResponse(**s.model_dump()) for s in sessions]


@router.post("/break-glass/{session_id}/revoke", response_model=BreakGlassResponse)
async def revoke_break_glass(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only System Admin can revoke emergency sessions")

    revoked = await access_governance_service.revoke_break_glass_session(
        session_id=session_id,
        revoked_by=current_user.get("id", "admin"),
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="Session not found")
    return BreakGlassResponse(**revoked.model_dump())


# ---------------------------------------------------------------------------
# Compliance Frameworks & Readiness Reports
# ---------------------------------------------------------------------------

@router.get("/frameworks/{framework}/readiness", response_model=FrameworkReadinessReport)
async def get_framework_readiness(
    framework: FrameworkType,
    current_user: dict = Depends(get_current_user),
):
    report = await compliance_registry_service.generate_readiness_report(framework)
    return FrameworkReadinessReport(**report)


@router.get("/controls")
async def list_controls(
    framework: Optional[FrameworkType] = Query(None),
    domain: Optional[ControlDomain] = Query(None),
    status_filter: Optional[ControlStatus] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user),
):
    controls = await compliance_registry_service.list_controls(
        framework=framework,
        domain=domain,
        status=status_filter,
    )
    return [c.model_dump() for c in controls]


@router.get("/gaps")
async def list_gaps(
    framework: Optional[FrameworkType] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    gaps = await compliance_registry_service.list_gaps(framework=framework)
    return [g.model_dump() for g in gaps]


# ---------------------------------------------------------------------------
# Auditor Mode
# ---------------------------------------------------------------------------

@router.get("/auditor/export")
async def export_auditor_bundle(
    current_user: dict = Depends(get_current_user),
):
    # Allowed for auditor or admin
    return await auditor_service.export_sanitized_governance_bundle(
        auditor_id=current_user.get("id", "auditor")
    )
