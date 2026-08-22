"""
TourSafe Analytics and Intelligence API Endpoints

Provides REST endpoints for authority operations overview, incident analytics,
zone intelligence, spatial heatmaps, anomaly conversion, responder performance,
notification health, data quality dashboards, tourist trip summaries, and data exports.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse

from ..routers.auth import get_current_user, require_role
from ..schemas.analytics import (
    AnalyticsFilterParams,
    AnomalyAnalyticsResponse,
    DataQualityDashboardResponse,
    ExportJobCreateRequest,
    ExportJobResponse,
    HeatmapMetricType,
    HeatmapResponse,
    IncidentAnalyticsResponse,
    NotificationAnalyticsResponse,
    OperationsOverviewMetrics,
    ResponderAnalyticsResponse,
    SafetyStateAnalyticsResponse,
    TimeGranularity,
    TouristAnalyticsResponse,
    ZoneDetailAnalyticsResponse,
    ZoneListAnalyticsResponse,
)
from ..services.analytics.analytics_service import analytics_service
from ..services.analytics.export_service import export_service

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


# ---------------------------------------------------------------------------
# 1. Operations Overview
# ---------------------------------------------------------------------------
@router.get(
    "/overview",
    response_model=OperationsOverviewMetrics,
    summary="Operations Overview KPIs and Trends",
)
async def get_overview(
    start_time: Optional[str] = Query(None, description="ISO8601 UTC start time"),
    end_time: Optional[str] = Query(None, description="ISO8601 UTC end time"),
    timezone: str = Query("UTC", description="Client timezone"),
    granularity: TimeGranularity = Query(TimeGranularity.DAY, description="Time granularity"),
    bypass_cache: bool = Query(False, description="Bypass analytical cache"),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required for operational analytics",
        )

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        timezone=timezone,
        granularity=granularity,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_operations_overview(tenant_id=user_id, params=params)


# ---------------------------------------------------------------------------
# 2. Incident Analytics
# ---------------------------------------------------------------------------
@router.get(
    "/incidents",
    response_model=IncidentAnalyticsResponse,
    summary="Incident Lifecycle, Duration Percentiles, and SLA Analytics",
)
async def get_incidents_analytics(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    granularity: TimeGranularity = Query(TimeGranularity.DAY),
    severity: Optional[str] = Query(None),
    incident_source: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        granularity=granularity,
        severity=severity,
        incident_source=incident_source,
        zone_id=zone_id,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_incident_analytics(tenant_id=user_id, params=params)


# ---------------------------------------------------------------------------
# 3. Zone Analytics
# ---------------------------------------------------------------------------
@router.get(
    "/zones",
    response_model=ZoneListAnalyticsResponse,
    summary="Zone Intelligence, Dwell Times, and Transition Summaries",
)
async def get_zones_analytics(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        risk_level=risk_level,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_zone_list_analytics(tenant_id=user_id, params=params)


@router.get(
    "/zones/{zone_id}",
    response_model=ZoneDetailAnalyticsResponse,
    summary="Individual Zone Deep-Dive Analytics",
)
async def get_zone_detail(
    zone_id: str,
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    granularity: TimeGranularity = Query(TimeGranularity.DAY),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        granularity=granularity,
        bypass_cache=bypass_cache,
    )
    try:
        return await analytics_service.get_zone_detail_analytics(
            tenant_id=user_id,
            zone_id=zone_id,
            params=params,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ---------------------------------------------------------------------------
# 4. Spatial Heatmaps
# ---------------------------------------------------------------------------
@router.get(
    "/heatmaps",
    response_model=HeatmapResponse,
    summary="Aggregated Spatial Grid Heatmap with Privacy Suppression",
)
async def get_heatmaps(
    layer: HeatmapMetricType = Query(HeatmapMetricType.TOURIST_DENSITY, description="Layer metric type"),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_spatial_heatmaps(
        tenant_id=user_id,
        metric_type=layer,
        params=params,
    )


# ---------------------------------------------------------------------------
# 5. Anomaly Analytics
# ---------------------------------------------------------------------------
@router.get(
    "/anomalies",
    response_model=AnomalyAnalyticsResponse,
    summary="ML Anomaly Episodes and Incident Conversion Analytics",
)
async def get_anomaly_analytics(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    granularity: TimeGranularity = Query(TimeGranularity.DAY),
    model_version: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        granularity=granularity,
        model_version=model_version,
        zone_id=zone_id,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_anomaly_analytics(tenant_id=user_id, params=params)


# ---------------------------------------------------------------------------
# 6. Safety State Analytics
# ---------------------------------------------------------------------------
@router.get(
    "/safety",
    response_model=SafetyStateAnalyticsResponse,
    summary="Safety State Engine Transition and Decision Distribution",
)
async def get_safety_analytics(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    granularity: TimeGranularity = Query(TimeGranularity.DAY),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        granularity=granularity,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_safety_state_analytics(tenant_id=user_id, params=params)


# ---------------------------------------------------------------------------
# 7. Responder Operational Analytics
# ---------------------------------------------------------------------------
@router.get(
    "/responders",
    response_model=ResponderAnalyticsResponse,
    summary="Responder and Unit Operational Performance Analytics",
)
async def get_responder_analytics(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    responder_id: Optional[str] = Query(None),
    unit_id: Optional[str] = Query(None),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        responder_id=responder_id,
        unit_id=unit_id,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_responder_analytics(tenant_id=user_id, params=params)


# ---------------------------------------------------------------------------
# 8. Notification Analytics
# ---------------------------------------------------------------------------
@router.get(
    "/notifications",
    response_model=NotificationAnalyticsResponse,
    summary="Notification Delivery Health and Provider Performance",
)
async def get_notification_analytics(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_notification_analytics(tenant_id=user_id, params=params)


# ---------------------------------------------------------------------------
# 9. Data Quality Dashboard
# ---------------------------------------------------------------------------
@router.get(
    "/data-quality",
    response_model=DataQualityDashboardResponse,
    summary="Data Quality, Sensor Completeness, and System Health",
)
async def get_data_quality(
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )
    return await analytics_service.get_data_quality_dashboard()


# ---------------------------------------------------------------------------
# 10. Tourist Self-Analytics & Authority Tourist Deep-Dive
# ---------------------------------------------------------------------------
@router.get(
    "/tourist/my-stats",
    response_model=TouristAnalyticsResponse,
    summary="Tourist Self-Service Trip & Safety History Analytics",
)
async def get_my_tourist_stats(
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    params = AnalyticsFilterParams()
    return await analytics_service.get_tourist_analytics(tourist_id=user_id, params=params)


@router.get(
    "/tourists/{tourist_id}",
    response_model=TouristAnalyticsResponse,
    summary="Authority View of Tourist Safety History",
)
async def get_tourist_history(
    tourist_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required to inspect tourist history",
        )
    params = AnalyticsFilterParams()
    return await analytics_service.get_tourist_analytics(tourist_id=tourist_id, params=params)


# ---------------------------------------------------------------------------
# 11. Data Export Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/export",
    response_model=ExportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate Asynchronous Analytical Data Export",
)
async def create_export(
    req: ExportJobCreateRequest,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required for data exports",
        )
    return await export_service.create_export_job(
        requested_by=user_id,
        tenant_id=user_id,
        req=req,
    )


@router.get(
    "/export/{job_id}",
    response_model=ExportJobResponse,
    summary="Check Export Job Status",
)
async def get_export_status(
    job_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    job = await export_service.get_export_job(job_id=job_id, requested_by=user_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found")
    return job


@router.get(
    "/export/{job_id}/download",
    summary="Download Generated Analytical Export File",
)
async def download_export(
    job_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role = user_id_role
    try:
        payload_str, filename, media_type = await export_service.get_export_payload(
            job_id=job_id,
            user_id=user_id,
            role=role,
        )
        if payload_str is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export file not found or not ready")

        return Response(
            content=payload_str,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
