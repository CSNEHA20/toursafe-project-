"""
TourSafe Security Governance & Monitoring Router.
Exposes administrative endpoints for:
- Security posture metrics & live security event telemetry
- Token and session revocation management
- Audit log cryptographic hash-chain verification & tamper detection
- Outbound URL SSRF compliance testing
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from ..core.rate_limiter import admin_rate_limiter
from ..core.security import revoke_token, revoke_session, is_token_revoked
from ..core.ssrf_protection import validate_outbound_url
from ..routers.auth import get_current_user, require_role
from ..services.governance.audit_service import audit_service
from ..services.security.security_events import security_event_service

router = APIRouter(prefix="/api/v1/admin/security", tags=["Security Governance & Threat Monitoring"])


class TokenRevokeRequest(BaseModel):
    token_or_jti: Optional[str] = None
    session_id: Optional[str] = None
    reason: str = Field(..., min_length=3)


class URLValidationRequest(BaseModel):
    url: str
    allowlist_domains: Optional[List[str]] = None


@router.get("/metrics", summary="Get Security Posture & Incident Overview")
async def get_security_metrics(
    user_id: str = Depends(require_role("admin", "authority_admin", "system_admin")),
):
    """Retrieve security monitoring metrics, failed logins, and threat alerts."""
    return await security_event_service.get_security_metrics()


@router.get("/events", summary="Query Security Events Stream")
async def query_security_events(
    event_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(require_role("admin", "authority_admin", "system_admin")),
):
    """Filter and query security event telemetry."""
    return await security_event_service.query_events(
        event_type=event_type,
        severity=severity,
        limit=limit,
    )


@router.post("/tokens/revoke", summary="Revoke Token or Session")
async def revoke_security_token(
    payload: TokenRevokeRequest,
    user_id: str = Depends(require_role("admin", "authority_admin", "system_admin")),
):
    """Administrative security action to revoke a compromised token or session."""
    if payload.token_or_jti:
        revoked = revoke_token(payload.token_or_jti)
        await security_event_service.record_event(
            event_type="auth.token.revoked",
            severity="HIGH",
            actor_id=user_id,
            details={"jti_or_token": payload.token_or_jti[:10] + "...", "reason": payload.reason},
        )
        return {"revoked": revoked, "target": "token"}
    elif payload.session_id:
        revoked = revoke_session(payload.session_id)
        await security_event_service.record_event(
            event_type="auth.session.revoked",
            severity="HIGH",
            actor_id=user_id,
            details={"session_id": payload.session_id, "reason": payload.reason},
        )
        return {"revoked": revoked, "target": "session"}

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Either 'token_or_jti' or 'session_id' must be specified.",
    )


@router.get("/audit/verify", summary="Verify Audit Hash Chain Integrity")
async def verify_audit_integrity(
    limit: int = Query(100, ge=1, le=500),
    user_id: str = Depends(require_role("admin", "authority_admin", "system_admin")),
):
    """Cryptographically verifies the SHA-256 hash chain of the audit log."""
    return await audit_service.verify_audit_chain(limit=limit)


@router.post("/validate-url", summary="Test SSRF Protection on Outbound URL")
async def validate_url_security(
    payload: URLValidationRequest,
    user_id: str = Depends(require_role("admin", "authority_admin", "system_admin")),
):
    """Validates an outbound integration URL against the SSRF defense policy."""
    try:
        clean_url = validate_outbound_url(
            url=payload.url,
            allowlist_domains=payload.allowlist_domains,
        )
        return {"valid": True, "clean_url": clean_url, "status": "APPROVED"}
    except HTTPException as exc:
        await security_event_service.record_event(
            event_type="ssrf.blocked",
            severity="MEDIUM",
            actor_id=user_id,
            details={"attempted_url": payload.url, "reason": exc.detail},
        )
        raise exc
