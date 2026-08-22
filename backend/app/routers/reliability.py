"""
TourSafe Reliability, Observability, SLO, Chaos & Disaster Recovery Router.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from ..core.reliability.metrics import metrics_collector
from ..core.reliability.degradation import degradation_manager, SystemMode, ServicePriority
from ..core.reliability.queue_resilience import dead_letter_manager
from ..core.reliability.db_resilience import slow_query_tracker
from ..services.reliability.backup_service import backup_service
from ..services.reliability.restore_service import restore_service
from ..services.reliability.chaos_engine import chaos_engine
from ..services.reliability.incident_timeline import incident_timeline_service
from .auth import get_current_user

router = APIRouter(prefix="/api/v1/reliability", tags=["Reliability & Observability"])


# --- Schemas ---

class DegradationModeRequest(BaseModel):
    mode: SystemMode
    reason: str = Field(..., min_length=3, max_length=255)


class ReplayJobRequest(BaseModel):
    job_id: str


class CreateBackupRequest(BaseModel):
    collections: Optional[List[str]] = None


class RestoreBackupRequest(BaseModel):
    backup_id: str
    dry_run: bool = True
    target_collections: Optional[List[str]] = None


# --- Endpoints ---

@router.get("/metrics")
async def get_system_metrics():
    """Returns central Golden Signals and subsystem-specific metrics in JSON format."""
    return metrics_collector.get_all_metrics()


@router.get("/slow-queries")
async def get_slow_queries(current_user: dict = Depends(get_current_user)):
    """List detected slow database queries (>100ms). Admin / Authority only."""
    if current_user.get("role") not in ["authority", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Authority access required")
    return {
        "count": len(slow_query_tracker.get_slow_queries()),
        "slow_queries": slow_query_tracker.get_slow_queries(),
    }


@router.get("/slo")
async def get_slo_status():
    """
    Returns platform SLOs, measured SLIs, error budget calculations,
    and current compliance status based on empirical metrics.
    """
    metrics = metrics_collector.get_all_metrics()
    golden = metrics["golden_signals"]
    subsystems = metrics["subsystems"]

    total_requests = golden["traffic"]["total_requests"]
    req_5xx = golden["traffic"]["requests_5xx"]
    p95_latency = golden["latency_ms"]["p95"]

    # Calculate actuals
    actual_api_avail = 100.0 if total_requests == 0 else round((1 - (req_5xx / total_requests)) * 100, 3)
    
    sos_received = subsystems["incident_operations"]["sos_signals_received"]
    sos_failures = subsystems["incident_operations"]["sos_processing_failures"]
    actual_sos_success = 100.0 if sos_received == 0 else round((1 - (sos_failures / sos_received)) * 100, 3)

    telemetry_total = subsystems["telemetry"]["packets_ingested"] + subsystems["telemetry"]["packets_dropped"]
    telemetry_dropped = subsystems["telemetry"]["packets_dropped"]
    actual_telemetry_success = 100.0 if telemetry_total == 0 else round((1 - (telemetry_dropped / telemetry_total)) * 100, 3)

    slos = [
        {
            "name": "API Availability",
            "target": 99.9,
            "window": "30d rolling",
            "sli_formula": "(1 - (5xx_requests / total_requests)) * 100",
            "actual": actual_api_avail,
            "status": "HEALTHY" if actual_api_avail >= 99.9 else "BUDGET_AT_RISK",
            "error_budget_remaining_percent": max(0.0, round((actual_api_avail - 99.0) / 0.9 * 100, 1)) if actual_api_avail < 99.9 else 100.0,
        },
        {
            "name": "API Latency (p95)",
            "target_ms": 250,
            "window": "5m rolling",
            "sli_formula": "p95_http_duration_ms",
            "actual_ms": p95_latency,
            "status": "HEALTHY" if p95_latency <= 250 else "DEGRADED",
        },
        {
            "name": "SOS Ingestion Reliability",
            "target": 99.99,
            "window": "30d rolling",
            "sli_formula": "(1 - (sos_failures / sos_received)) * 100",
            "actual": actual_sos_success,
            "status": "HEALTHY" if actual_sos_success >= 99.99 else "CRITICAL_BREACH",
            "error_budget_remaining_percent": 100.0 if sos_failures == 0 else 0.0,
        },
        {
            "name": "Telemetry Ingestion Success",
            "target": 99.5,
            "window": "24h rolling",
            "sli_formula": "(1 - (dropped_packets / total_packets)) * 100",
            "actual": actual_telemetry_success,
            "status": "HEALTHY" if actual_telemetry_success >= 99.5 else "DEGRADED",
        },
    ]

    return {
        "timestamp": metrics["timestamp"],
        "slos": slos,
        "policy_recommendation": "Normal operations. Deployments permitted." if all(s["status"] == "HEALTHY" for s in slos) else "Caution: Error budget consumption elevated. Avoid high-risk deploys.",
    }


@router.get("/degradation")
async def get_degradation_status():
    """Returns current system degradation mode, reason, and active priority allowances."""
    return degradation_manager.get_status()


@router.post("/degradation/mode")
async def update_degradation_mode(
    req: DegradationModeRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update system degradation mode (Admin / Authority only)."""
    if current_user.get("role") not in ["authority", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Authority or Admin privileges required")
    
    degradation_manager.set_mode(req.mode, req.reason, actor_id=current_user.get("user_id", "admin"))
    return {
        "success": True,
        "new_mode": degradation_manager.current_mode.value,
        "reason": degradation_manager.reason,
    }


@router.get("/queues/dead-letter")
async def list_dead_letters(
    queue_name: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user)
):
    """Inspect dead-letter queue items (Admin only)."""
    if current_user.get("role") not in ["authority", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Authority or Admin privileges required")
    
    items = await dead_letter_manager.list_dead_letters(queue_name=queue_name, limit=limit)
    return {"total": len(items), "dead_letters": items}


@router.post("/queues/dead-letter/replay")
async def replay_dead_letter(
    req: ReplayJobRequest,
    current_user: dict = Depends(get_current_user)
):
    """Replay a dead-letter queue job idempotently (Admin only)."""
    if current_user.get("role") not in ["authority", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Authority or Admin privileges required")

    async def default_replay_handler(payload):
        # Default generic handler acknowledging replay
        return {"processed": True}

    res = await dead_letter_manager.replay_message(
        job_id=req.job_id,
        handler=default_replay_handler,
        actor_id=current_user.get("user_id", "admin")
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/backups/create")
async def create_backup(
    req: CreateBackupRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a verified snapshot backup of platform data (Admin only)."""
    if current_user.get("role") not in ["authority", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Authority or Admin privileges required")
    
    metadata = await backup_service.create_backup(
        collections=req.collections,
        actor_id=current_user.get("user_id", "admin")
    )
    return metadata


@router.get("/backups")
async def list_backups(
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    """List cataloged system backups (Admin only)."""
    if current_user.get("role") not in ["authority", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Authority or Admin privileges required")
    
    backups = await backup_service.list_backups(limit=limit)
    return {"total": len(backups), "backups": backups}


@router.post("/backups/restore")
async def restore_backup(
    req: RestoreBackupRequest,
    current_user: dict = Depends(get_current_user)
):
    """Execute a dry-run or actual restoration from backup (Admin only)."""
    if current_user.get("role") not in ["authority", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Authority or Admin privileges required")

    res = await restore_service.restore_from_backup(
        backup_id=req.backup_id,
        dry_run=req.dry_run,
        actor_id=current_user.get("user_id", "admin"),
        target_collections=req.target_collections,
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/chaos/run")
async def run_chaos_suite(current_user: dict = Depends(get_current_user)):
    """Execute the controlled chaos and resilience drill suite (Admin only)."""
    if current_user.get("role") not in ["authority", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Authority or Admin privileges required")

    result = await chaos_engine.run_full_resilience_suite()
    return result


@router.get("/incidents/{incident_id}/timeline")
async def get_incident_timeline(
    incident_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Reconstruct a unified cross-subsystem chronological timeline for an incident."""
    if current_user.get("role") not in ["authority", "responder", "admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Operational access required")

    timeline = await incident_timeline_service.get_incident_timeline(incident_id)
    return timeline
