"""
TourSafe Analytics and Intelligence API Endpoints (Prompt 26)

Provides REST endpoints for authority executive operations overview, incident intelligence,
geospatial hotspots and flow graphs, zone intelligence, spatial heatmaps, anomaly conversion,
responder performance & SLA percentiles, escalation analytics, notification health,
data quality dashboards, system performance, demand forecasting with uncertainty intervals,
operational recommendations, analytics alerts, metric catalog, tourist trip summaries, and data exports.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse

from ..core import database as db_core
from ..routers.auth import get_current_user, require_role
from ..schemas.analytics import (
    AnalyticsAlertListResponse,
    AnalyticsAlertRecord,
    AnalyticsAuditLogEntry,
    AnalyticsFilterParams,
    AnomalyAnalyticsResponse,
    DataQualityDashboardResponse,
    DensityAlertResponse,
    EscalationAnalyticsResponse,
    ExecutiveDashboardResponse,
    ExportJobCreateRequest,
    ExportJobResponse,
    ForecastDemandResponse,
    ForecastHorizon,
    GeospatialHotspotResponse,
    HeatmapMetricType,
    HeatmapResponse,
    IncidentAnalyticsResponse,
    MetricCatalogResponse,
    ModelPerformanceReportResponse,
    NotificationAnalyticsResponse,
    OperationalRecommendationsResponse,
    OperationsOverviewMetrics,
    ResponderAnalyticsResponse,
    RouteAnalyticsResponse,
    SafetyStateAnalyticsResponse,
    SystemPerformanceResponse,
    TimeGranularity,
    TimeWindowType,
    TouristAnalyticsResponse,
    TouristFlowResponse,
    ZoneDetailAnalyticsResponse,
    ZoneListAnalyticsResponse,
)
from ..services.analytics.analytics_service import analytics_service
from ..services.analytics.audit_service import analytics_audit_service
from ..services.analytics.export_service import export_service

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def _extract_authority_context(user_id_role: tuple) -> tuple[str, str, Optional[str]]:
    """
    Extracts user_id, role, and jurisdiction_id.
    """
    user_id, role = user_id_role[0], user_id_role[1]
    # If user object contains jurisdiction info in token or profile
    jurisdiction_id = None
    return user_id, role, jurisdiction_id


# ---------------------------------------------------------------------------
# 1. Executive Operations Overview
# ---------------------------------------------------------------------------
@router.get(
    "/executive",
    response_model=ExecutiveDashboardResponse,
    summary="Executive Dashboard Operational Intelligence & KPIs",
)
async def get_executive_dashboard(
    start_time: Optional[str] = Query(None, description="ISO8601 UTC start time"),
    end_time: Optional[str] = Query(None, description="ISO8601 UTC end time"),
    time_window: Optional[TimeWindowType] = Query(None, description="LIVE, TODAY, LAST_24_HOURS, LAST_7_DAYS, LAST_30_DAYS, CUSTOM"),
    timezone: str = Query("UTC", description="Client / Authority timezone"),
    jurisdiction_id: Optional[str] = Query(None, description="Jurisdiction filter"),
    bypass_cache: bool = Query(False, description="Bypass analytical cache"),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required for executive analytics",
        )

    # Multi-tenancy enforcement: non-admin authority cannot inspect other jurisdictions
    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        time_window=time_window,
        timezone=timezone,
        jurisdiction_id=effective_jurisdiction,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_executive_overview(
        tenant_id=user_id,
        params=params,
        jurisdiction_id=effective_jurisdiction,
    )


@router.get(
    "/overview",
    response_model=OperationsOverviewMetrics,
    summary="Operations Overview KPIs and Trends (Backward Compatible)",
)
async def get_overview(
    start_time: Optional[str] = Query(None, description="ISO8601 UTC start time"),
    end_time: Optional[str] = Query(None, description="ISO8601 UTC end time"),
    time_window: Optional[TimeWindowType] = Query(None),
    timezone: str = Query("UTC", description="Client timezone"),
    granularity: TimeGranularity = Query(TimeGranularity.DAY, description="Time granularity"),
    bypass_cache: bool = Query(False, description="Bypass analytical cache"),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required for operational analytics",
        )

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        time_window=time_window,
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
    summary="Incident Lifecycle, Duration Percentiles, Aging Analysis, and SLA Analytics",
)
async def get_incidents_analytics(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    time_window: Optional[TimeWindowType] = Query(None),
    timezone: str = Query("UTC"),
    granularity: TimeGranularity = Query(TimeGranularity.DAY),
    severity: Optional[str] = Query(None),
    incident_source: Optional[str] = Query(None),
    incident_type: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    jurisdiction_id: Optional[str] = Query(None),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        time_window=time_window,
        timezone=timezone,
        granularity=granularity,
        severity=severity,
        incident_source=incident_source,
        incident_type=incident_type,
        zone_id=zone_id,
        jurisdiction_id=effective_jurisdiction,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_incident_analytics(
        tenant_id=user_id,
        params=params,
        jurisdiction_id=effective_jurisdiction,
    )


# ---------------------------------------------------------------------------
# 3. Zone Analytics & Intelligence
# ---------------------------------------------------------------------------
@router.get(
    "/zones",
    response_model=ZoneListAnalyticsResponse,
    summary="Zone Intelligence, Risk Ranking, and Dwell Summaries",
)
async def get_zones_analytics(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    time_window: Optional[TimeWindowType] = Query(None),
    risk_level: Optional[str] = Query(None),
    jurisdiction_id: Optional[str] = Query(None),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        time_window=time_window,
        risk_level=risk_level,
        jurisdiction_id=effective_jurisdiction,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_zone_list_analytics(
        tenant_id=user_id,
        params=params,
        jurisdiction_id=effective_jurisdiction,
    )


@router.get(
    "/zones/{zone_id}",
    response_model=ZoneDetailAnalyticsResponse,
    summary="Individual Zone Deep-Dive Analytics",
)
async def get_zone_detail(
    zone_id: str,
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    time_window: Optional[TimeWindowType] = Query(None),
    granularity: TimeGranularity = Query(TimeGranularity.DAY),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        time_window=time_window,
        granularity=granularity,
        bypass_cache=bypass_cache,
    )
    try:
        return await analytics_service.get_zone_detail_analytics(
            tenant_id=user_id,
            zone_id=zone_id,
            params=params,
            jurisdiction_id=default_jurisdiction,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ---------------------------------------------------------------------------
# 4. Geospatial Intelligence & Hotspots
# ---------------------------------------------------------------------------
@router.get(
    "/geospatial/hotspots",
    response_model=GeospatialHotspotResponse,
    summary="Geospatial Incident and Risk Hotspots",
)
async def get_hotspots(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    time_window: Optional[TimeWindowType] = Query(None),
    jurisdiction_id: Optional[str] = Query(None),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        time_window=time_window,
        jurisdiction_id=effective_jurisdiction,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_geospatial_hotspots(
        tenant_id=user_id,
        params=params,
        jurisdiction_id=effective_jurisdiction,
    )


@router.get(
    "/heatmaps",
    response_model=HeatmapResponse,
    summary="Aggregated Spatial Grid Heatmap with Privacy Suppression",
)
async def get_heatmaps(
    layer: HeatmapMetricType = Query(HeatmapMetricType.TOURIST_DENSITY, description="Layer metric type"),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    time_window: Optional[TimeWindowType] = Query(None),
    jurisdiction_id: Optional[str] = Query(None),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        time_window=time_window,
        jurisdiction_id=effective_jurisdiction,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_spatial_heatmaps(
        tenant_id=user_id,
        metric_type=layer,
        params=params,
        jurisdiction_id=effective_jurisdiction,
    )


@router.get(
    "/geospatial/flow",
    response_model=TouristFlowResponse,
    summary="Aggregated Tourist Flow and Zone Transition Corridors",
)
async def get_tourist_flow(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    time_window: Optional[TimeWindowType] = Query(None),
    jurisdiction_id: Optional[str] = Query(None),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority permissions required")

    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        time_window=time_window,
        jurisdiction_id=effective_jurisdiction,
    )
    return await analytics_service.get_tourist_flow_analytics(
        tenant_id=user_id,
        params=params,
        jurisdiction_id=effective_jurisdiction,
    )


@router.get(
    "/geospatial/routes",
    response_model=RouteAnalyticsResponse,
    summary="Itinerary and Route Deviation Analytics",
)
async def get_route_analytics(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    time_window: Optional[TimeWindowType] = Query(None),
    jurisdiction_id: Optional[str] = Query(None),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority permissions required")

    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        time_window=time_window,
        jurisdiction_id=effective_jurisdiction,
    )
    return await analytics_service.get_route_analytics(
        tenant_id=user_id,
        params=params,
        jurisdiction_id=effective_jurisdiction,
    )


@router.get(
    "/geospatial/density-alerts",
    response_model=DensityAlertResponse,
    summary="High Concentration Density Alerts",
)
async def get_density_alerts(
    jurisdiction_id: Optional[str] = Query(None),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority permissions required")

    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)
    return await analytics_service.get_density_alerts(jurisdiction_id=effective_jurisdiction)


# ---------------------------------------------------------------------------
# 5. Responder Operational & Escalation Analytics
# ---------------------------------------------------------------------------
@router.get(
    "/responders",
    response_model=ResponderAnalyticsResponse,
    summary="Responder Operational Performance & SLA Percentiles",
)
async def get_responder_analytics(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    time_window: Optional[TimeWindowType] = Query(None),
    responder_id: Optional[str] = Query(None),
    unit_id: Optional[str] = Query(None),
    jurisdiction_id: Optional[str] = Query(None),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        time_window=time_window,
        responder_id=responder_id,
        unit_id=unit_id,
        jurisdiction_id=effective_jurisdiction,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_responder_analytics(
        tenant_id=user_id,
        params=params,
        jurisdiction_id=effective_jurisdiction,
    )


@router.get(
    "/escalations",
    response_model=EscalationAnalyticsResponse,
    summary="Incident Escalation Frequency, Levels, and Root Causes",
)
async def get_escalation_analytics(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    time_window: Optional[TimeWindowType] = Query(None),
    jurisdiction_id: Optional[str] = Query(None),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        time_window=time_window,
        jurisdiction_id=effective_jurisdiction,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_escalation_analytics(
        tenant_id=user_id,
        params=params,
        jurisdiction_id=effective_jurisdiction,
    )


# ---------------------------------------------------------------------------
# 6. Safety State & Anomaly Analytics
# ---------------------------------------------------------------------------
@router.get(
    "/safety",
    response_model=SafetyStateAnalyticsResponse,
    summary="Safety State Engine Transition, Unknown Reliability, and Risk Episodes",
)
async def get_safety_analytics(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    time_window: Optional[TimeWindowType] = Query(None),
    granularity: TimeGranularity = Query(TimeGranularity.DAY),
    jurisdiction_id: Optional[str] = Query(None),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        time_window=time_window,
        granularity=granularity,
        jurisdiction_id=effective_jurisdiction,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_safety_state_analytics(
        tenant_id=user_id,
        params=params,
        jurisdiction_id=effective_jurisdiction,
    )


@router.get(
    "/anomalies",
    response_model=AnomalyAnalyticsResponse,
    summary="ML Anomaly Episodes, Persistence, and Incident Conversion Analytics",
)
async def get_anomaly_analytics(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    time_window: Optional[TimeWindowType] = Query(None),
    granularity: TimeGranularity = Query(TimeGranularity.DAY),
    model_version: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    jurisdiction_id: Optional[str] = Query(None),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        time_window=time_window,
        granularity=granularity,
        model_version=model_version,
        zone_id=zone_id,
        jurisdiction_id=effective_jurisdiction,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_anomaly_analytics(
        tenant_id=user_id,
        params=params,
        jurisdiction_id=effective_jurisdiction,
    )


@router.get(
    "/models/performance",
    response_model=ModelPerformanceReportResponse,
    summary="ML Models Performance, Drift Detection, and Latency Report",
)
async def get_model_performance(
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, _ = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority permissions required")

    return await analytics_service.get_model_performance_report(tenant_id=user_id)


# ---------------------------------------------------------------------------
# 7. Notification & Telemetry Health
# ---------------------------------------------------------------------------
@router.get(
    "/notifications",
    response_model=NotificationAnalyticsResponse,
    summary="Notification Delivery Health and Provider Performance",
)
async def get_notification_analytics(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    time_window: Optional[TimeWindowType] = Query(None),
    bypass_cache: bool = Query(False),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, _ = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )

    params = AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        time_window=time_window,
        bypass_cache=bypass_cache,
    )
    return await analytics_service.get_notification_analytics(tenant_id=user_id, params=params)


@router.get(
    "/data-quality",
    response_model=DataQualityDashboardResponse,
    summary="Data Quality, Sensor Completeness, and Device Health",
)
async def get_data_quality(
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, _ = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required",
        )
    return await analytics_service.get_data_quality_dashboard()


@router.get(
    "/system",
    response_model=SystemPerformanceResponse,
    summary="System Performance, Background Jobs, and Service Latencies",
)
async def get_system_performance(
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, _ = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority permissions required")

    return await analytics_service.get_system_performance()


# ---------------------------------------------------------------------------
# 8. Demand Forecasting & Operational Recommendations
# ---------------------------------------------------------------------------
@router.get(
    "/forecasts",
    response_model=ForecastDemandResponse,
    summary="Baseline Demand Forecasting with 80% Prediction Intervals",
)
async def get_forecast(
    metric_name: str = Query("incident_volume", description="incident_volume, responder_demand, tourist_density"),
    horizon: ForecastHorizon = Query(ForecastHorizon.NEXT_DAY),
    jurisdiction_id: Optional[str] = Query(None),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority permissions required")

    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)

    # Audit query
    await analytics_audit_service.log_action(
        action="QUERY_FORECAST",
        user_id=user_id,
        role=role,
        jurisdiction_id=effective_jurisdiction,
        details={"metric_name": metric_name, "horizon": horizon.value},
    )

    return await analytics_service.generate_demand_forecast(
        metric_name=metric_name,
        horizon=horizon,
        jurisdiction_id=effective_jurisdiction,
    )


@router.get(
    "/recommendations",
    response_model=OperationalRecommendationsResponse,
    summary="Explainable Non-Binding Operational Recommendations",
)
async def get_recommendations(
    jurisdiction_id: Optional[str] = Query(None),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority permissions required")

    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)
    return await analytics_service.generate_operational_recommendations(jurisdiction_id=effective_jurisdiction)


# ---------------------------------------------------------------------------
# 9. Analytics Alerts & Surge Detection
# ---------------------------------------------------------------------------
@router.get(
    "/alerts",
    response_model=AnalyticsAlertListResponse,
    summary="Active Operational & Analytics Alerts",
)
async def list_analytics_alerts(
    jurisdiction_id: Optional[str] = Query(None),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority permissions required")

    db = db_core.get_database()
    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)

    q: Dict[str, Any] = {"is_active": True}
    if effective_jurisdiction:
        q["jurisdiction_id"] = effective_jurisdiction

    cursor = db.analytics_alerts.find(q).sort("triggered_at", -1).limit(50)
    alerts: List[AnalyticsAlertRecord] = []
    async for doc in cursor:
        alerts.append(AnalyticsAlertRecord(**doc))

    return AnalyticsAlertListResponse(
        alerts=alerts,
        active_count=len(alerts),
        freshness=DataFreshnessMeta(freshness_status="LIVE"),
    )


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=Dict[str, Any],
    summary="Acknowledge Analytics Alert",
)
async def acknowledge_alert(
    alert_id: str,
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority permissions required")

    db = db_core.get_database()
    now_iso = db_core.settings.now_iso if hasattr(db_core.settings, "now_iso") else ""
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    res = await db.analytics_alerts.update_one(
        {"alert_id": alert_id},
        {"$set": {"acknowledged_by": user_id, "acknowledged_at": now_iso, "is_active": False}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    await analytics_audit_service.log_action(
        action="ACK_ALERT",
        user_id=user_id,
        role=role,
        jurisdiction_id=default_jurisdiction,
        details={"alert_id": alert_id},
    )

    return {"status": "ACKNOWLEDGED", "alert_id": alert_id, "acknowledged_at": now_iso}


# ---------------------------------------------------------------------------
# 10. Metric Catalog & Audit Logs
# ---------------------------------------------------------------------------
@router.get(
    "/metric-catalog",
    response_model=MetricCatalogResponse,
    summary="Machine-Readable Metric Definitions and Data Lineage Catalog",
)
async def get_metric_catalog(
    user_id_role: tuple = Depends(get_current_user),
):
    return await analytics_service.get_metric_catalog()


@router.get(
    "/audit-logs",
    response_model=List[AnalyticsAuditLogEntry],
    summary="Analytics Platform Audit Trail",
)
async def get_audit_logs(
    jurisdiction_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, default_jurisdiction = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authority permissions required")

    effective_jurisdiction = jurisdiction_id if role == "admin" else (default_jurisdiction or jurisdiction_id)
    return await analytics_audit_service.get_audit_logs(jurisdiction_id=effective_jurisdiction, limit=limit)


# ---------------------------------------------------------------------------
# 11. Tourist Personal Analytics & Authority Deep-Dive
# ---------------------------------------------------------------------------
@router.get(
    "/tourist/my-stats",
    response_model=TouristAnalyticsResponse,
    summary="Tourist Self-Service Trip & Safety History Analytics",
)
async def get_my_tourist_stats(
    user_id_role: tuple = Depends(get_current_user),
):
    user_id, role, _ = _extract_authority_context(user_id_role)
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
    user_id, role, _ = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required to inspect tourist history",
        )
    params = AnalyticsFilterParams()
    return await analytics_service.get_tourist_analytics(tourist_id=tourist_id, params=params)


# ---------------------------------------------------------------------------
# 12. Data Export Endpoints
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
    user_id, role, _ = _extract_authority_context(user_id_role)
    if role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authority or Admin permissions required for data exports",
        )
    return await export_service.create_export_job(
        requested_by=user_id,
        tenant_id=user_id,
        req=req,
        role=role,
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
    user_id, role, _ = _extract_authority_context(user_id_role)
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
    user_id, role, _ = _extract_authority_context(user_id_role)
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
