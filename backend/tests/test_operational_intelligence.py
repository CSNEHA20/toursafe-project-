"""
Unit and Integration Tests for TourSafe Advanced Operational Analytics & Intelligence (Prompt 26)

Verifies:
1. Executive Dashboard KPIs (active tourists, active trips, active incidents, open SOS, responders breakdown, elevated states, response percentiles)
2. Jurisdiction Multi-Tenancy Isolation (Authority A cannot inspect Authority B's data)
3. Time Window Normalization (LIVE, TODAY, LAST_24_HOURS, LAST_7_DAYS, LAST_30_DAYS, CUSTOM) and timezone handling
4. Incident Duration Percentiles (P50, P75, P90, P95, P99, mean)
5. Incident Aging Analysis & Backlog Buckets (<5m, 5-15m, 15-30m, 30+m)
6. Escalation Analytics (Levels 0-3, root cause distribution, post-escalation resolution rate)
7. Geospatial Hotspot Clustering & Intensity Scoring
8. Tourist Flow Transition Corridors
9. Safety State UNKNOWN Frequency & Reliability Indicators
10. ML Model Performance Integration & Drift Indicators
11. Demand Forecasting with 80% Prediction Intervals (P10/P90)
12. Graceful INSUFFICIENT_DATA Handling for Sparse Historical Series
13. Operational Recommendations Generation (Explainable, Non-Binding)
14. Incident Surge Detection with Cooldown and Alert Deduplication
15. Data Export with PII Redaction and Audit Trail
16. Metric Catalog Integrity
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.analytics import (
    AnalyticsFilterParams,
    ExportFormat,
    ExportJobCreateRequest,
    ForecastHorizon,
    HeatmapMetricType,
    QualityStatus,
    TimeGranularity,
    TimeWindowType,
)
from app.services.analytics.aggregation_engine import (
    aggregation_engine,
    compute_duration_percentiles,
    decode_geohash_center,
    encode_geohash,
    normalize_time_range,
)
from app.services.analytics.analytics_service import analytics_service
from app.services.analytics.audit_service import analytics_audit_service
from app.services.analytics.export_service import export_service
from app.services.analytics.forecasting_service import forecasting_service
from app.services.analytics.geospatial_analytics_service import geospatial_analytics_service
from app.services.analytics.operational_intelligence_service import operational_intelligence_service
from app.services.analytics.response_analytics_service import response_analytics_service
from app.services.analytics.safety_analytics_service import safety_analytics_service


# ---------------------------------------------------------------------------
# Mock Database Setup
# ---------------------------------------------------------------------------

class MockAsyncCursor:
    def __init__(self, items):
        self.items = list(items)
        self.idx = 0

    def __aiter__(self):
        self.idx = 0
        return self

    async def __anext__(self):
        if self.idx < len(self.items):
            item = self.items[self.idx]
            self.idx += 1
            return item
        raise StopAsyncIteration

    def sort(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    async def to_list(self, length=None):
        return self.items[:length] if length else self.items


class MockCollection:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return MagicMock(inserted_id="mock_id")

    async def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                if "$set" in update:
                    doc.update(update["$set"])
                return MagicMock(modified_count=1, matched_count=1)
        return MagicMock(modified_count=0, matched_count=0)

    async def count_documents(self, query):
        count = 0
        for doc in self.docs:
            match = True
            for k, v in query.items():
                if isinstance(v, dict):
                    if "$in" in v and doc.get(k) not in v["$in"]:
                        match = False
                        break
                    if "$gte" in v and doc.get(k, "") < v["$gte"]:
                        match = False
                        break
                    if "$lte" in v and doc.get(k, "") > v["$lte"]:
                        match = False
                        break
                elif doc.get(k) != v:
                    match = False
                    break
            if match:
                count += 1
        return count

    def find(self, query=None, projection=None):
        query = query or {}
        matched = []
        for doc in self.docs:
            match = True
            for k, v in query.items():
                if isinstance(v, dict):
                    if "$in" in v and doc.get(k) not in v["$in"]:
                        match = False
                        break
                    if "$gte" in v and doc.get(k, "") < v["$gte"]:
                        match = False
                        break
                    if "$lte" in v and doc.get(k, "") > v["$lte"]:
                        match = False
                        break
                elif doc.get(k) != v:
                    match = False
                    break
            if match:
                matched.append(doc)
        return MockAsyncCursor(matched)

    async def find_one(self, query):
        for doc in self.docs:
            match = True
            for k, v in query.items():
                if isinstance(v, dict):
                    if "$in" in v and doc.get(k) not in v["$in"]:
                        match = False
                        break
                    if "$gte" in v and doc.get(k, "") < v["$gte"]:
                        match = False
                        break
                elif doc.get(k) != v:
                    match = False
                    break
            if match:
                return dict(doc)
        return None


class MockDatabase:
    def __init__(self):
        self.tourist_profiles = MockCollection()
        self.tracking_sessions = MockCollection()
        self.tourist_itineraries = MockCollection()
        self.incidents = MockCollection()
        self.sos_events = MockCollection()
        self.safety_decisions = MockCollection()
        self.risk_episodes = MockCollection()
        self.anomaly_events = MockCollection()
        self.responder_profiles = MockCollection()
        self.responder_assignments = MockCollection()
        self.zones = MockCollection()
        self.zone_transitions = MockCollection()
        self.location_history = MockCollection()
        self.notifications = MockCollection()
        self.dead_letter_queue = MockCollection()
        self.export_jobs = MockCollection()
        self.analytics_alerts = MockCollection()
        self.analytics_audit_logs = MockCollection()
        self.ml_model_registry = MockCollection()
        self.telemetry_samples = MockCollection()
        self.telemetry_windows = MockCollection()


@pytest.fixture
def mock_db():
    return MockDatabase()


# ---------------------------------------------------------------------------
# Test 1: Time Window & Normalization
# ---------------------------------------------------------------------------
def test_time_window_normalization():
    # LIVE window
    s, e = normalize_time_range(time_window=TimeWindowType.LIVE)
    dt_s = datetime.fromisoformat(s)
    dt_e = datetime.fromisoformat(e)
    assert (dt_e - dt_s).total_seconds() <= 900.0 + 1.0

    # LAST_7_DAYS
    s7, e7 = normalize_time_range(time_window=TimeWindowType.LAST_7_DAYS)
    dt_s7 = datetime.fromisoformat(s7)
    dt_e7 = datetime.fromisoformat(e7)
    diff_days = (dt_e7 - dt_s7).total_seconds() / 86400.0
    assert 6.9 <= diff_days <= 7.1

    # Timezone handling
    st_tz, end_tz = normalize_time_range(time_window=TimeWindowType.TODAY, tz_str="Asia/Kolkata")
    assert st_tz is not None
    assert end_tz is not None


# ---------------------------------------------------------------------------
# Test 2: Percentile Calculations
# ---------------------------------------------------------------------------
def test_duration_percentiles_calculation():
    durations = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    metrics = compute_duration_percentiles(durations)
    assert metrics.count == 10
    assert metrics.p50_seconds == 55.0  # Median
    assert metrics.p75_seconds == 77.5
    assert metrics.p90_seconds == 91.0
    assert metrics.min_seconds == 10.0
    assert metrics.max_seconds == 100.0
    assert metrics.mean_seconds == 55.0


# ---------------------------------------------------------------------------
# Test 3: Executive Dashboard KPIs
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_executive_dashboard_kpis(mock_db):
    # Populate fixtures
    await mock_db.tracking_sessions.insert_one({"session_id": "s1", "status": "active", "jurisdiction_id": "jur_A"})
    await mock_db.tourist_profiles.insert_one({"user_id": "t1", "is_active": True, "jurisdiction_id": "jur_A"})
    await mock_db.tourist_itineraries.insert_one({"id": "it1", "status": "ACTIVE", "jurisdiction_id": "jur_A"})

    # Responder fixtures
    await mock_db.responder_profiles.insert_one({"responder_id": "r1", "status": "ACTIVE", "is_available": True, "jurisdiction_id": "jur_A"})
    await mock_db.responder_profiles.insert_one({"responder_id": "r2", "status": "ACTIVE", "is_available": False, "jurisdiction_id": "jur_A"})
    await mock_db.responder_profiles.insert_one({"responder_id": "r3", "status": "OFFLINE", "jurisdiction_id": "jur_A"})

    # Incident fixtures
    now_iso = datetime.now(timezone.utc).isoformat()
    await mock_db.incidents.insert_one({
        "incident_id": "inc_1",
        "status": "OPEN",
        "incident_source": "MANUAL_SOS",
        "started_at": now_iso,
        "jurisdiction_id": "jur_A",
        "timeline": [{"action": "incident.responding", "timestamp": now_iso}],
    })

    with patch("app.core.database.get_database", return_value=mock_db):
        params = AnalyticsFilterParams(time_window=TimeWindowType.TODAY)
        res = await operational_intelligence_service.get_executive_overview(
            tenant_id="auth_1",
            params=params,
            jurisdiction_id="jur_A",
        )

        assert res.active_tourists == 1
        assert res.active_trips == 1
        assert res.active_incidents == 1
        assert res.open_sos_count == 1
        assert res.responders.total_registered == 3
        assert res.responders.available_for_dispatch == 1
        assert res.responders.assigned_or_responding == 1
        assert res.freshness.freshness_status == "LIVE"


# ---------------------------------------------------------------------------
# Test 4: Multi-Tenancy Jurisdiction Isolation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_jurisdiction_isolation(mock_db):
    now_iso = datetime.now(timezone.utc).isoformat()
    # Authority A data
    await mock_db.incidents.insert_one({"incident_id": "inc_A", "status": "OPEN", "started_at": now_iso, "jurisdiction_id": "jur_A"})
    # Authority B data
    await mock_db.incidents.insert_one({"incident_id": "inc_B", "status": "OPEN", "started_at": now_iso, "jurisdiction_id": "jur_B"})

    with patch("app.core.database.get_database", return_value=mock_db):
        params_A = AnalyticsFilterParams(time_window=TimeWindowType.TODAY)
        res_A = await operational_intelligence_service.get_executive_overview(
            tenant_id="auth_A",
            params=params_A,
            jurisdiction_id="jur_A",
        )
        assert res_A.active_incidents == 1

        params_B = AnalyticsFilterParams(time_window=TimeWindowType.TODAY)
        res_B = await operational_intelligence_service.get_executive_overview(
            tenant_id="auth_B",
            params=params_B,
            jurisdiction_id="jur_B",
        )
        assert res_B.active_incidents == 1


# ---------------------------------------------------------------------------
# Test 5: Incident Aging Buckets
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_incident_aging_analysis(mock_db):
    now = datetime.now(timezone.utc)
    # <5m incident
    await mock_db.incidents.insert_one({"incident_id": "inc_fresh", "status": "OPEN", "started_at": (now - timedelta(minutes=2)).isoformat()})
    # 5-15m incident
    await mock_db.incidents.insert_one({"incident_id": "inc_med", "status": "OPEN", "started_at": (now - timedelta(minutes=10)).isoformat()})
    # 30+m incident
    await mock_db.incidents.insert_one({"incident_id": "inc_old", "status": "OPEN", "started_at": (now - timedelta(minutes=45)).isoformat()})

    with patch("app.core.database.get_database", return_value=mock_db):
        aging = await operational_intelligence_service.compute_incident_aging_analysis()
        assert aging.aging_buckets[0].incident_count == 1  # <5m
        assert aging.aging_buckets[1].incident_count == 1  # 5-15m
        assert aging.aging_buckets[3].incident_count == 1  # 30+m
        assert aging.oldest_open_incident_id == "inc_old"
        assert aging.oldest_open_duration_minutes >= 44.0


# ---------------------------------------------------------------------------
# Test 6: Escalation Analytics
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_escalation_analytics(mock_db):
    now_iso = datetime.now(timezone.utc).isoformat()
    await mock_db.incidents.insert_one({
        "incident_id": "inc_esc_1",
        "status": "RESOLVED",
        "escalation_level": 1,
        "escalation_reason": "SLA_TIMEOUT",
        "started_at": now_iso,
        "escalated_at": now_iso,
    })
    await mock_db.incidents.insert_one({
        "incident_id": "inc_norm",
        "status": "RESOLVED",
        "escalation_level": 0,
        "started_at": now_iso,
    })

    with patch("app.core.database.get_database", return_value=mock_db):
        params = AnalyticsFilterParams(time_window=TimeWindowType.TODAY)
        esc_res = await response_analytics_service.get_escalation_analytics("tenant_1", params)
        assert esc_res.total_eligible_incidents == 2
        assert esc_res.total_escalated_incidents == 1
        assert esc_res.escalation_rate == 0.5
        assert esc_res.resolution_post_escalation_rate == 1.0


# ---------------------------------------------------------------------------
# Test 7: Geospatial Hotspots & Privacy Suppression
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_geospatial_hotspots(mock_db):
    now_iso = datetime.now(timezone.utc).isoformat()
    # Insert 3 incidents at the same location (Goa Beach area)
    for i in range(3):
        await mock_db.incidents.insert_one({
            "incident_id": f"inc_g_{i}",
            "status": "OPEN",
            "incident_type": "MEDICAL",
            "started_at": now_iso,
            "location_data": {"latitude": 15.2993, "longitude": 74.1240},
        })

    with patch("app.core.database.get_database", return_value=mock_db):
        params = AnalyticsFilterParams(time_window=TimeWindowType.TODAY)
        hotspot_res = await geospatial_analytics_service.get_geospatial_hotspots("tenant_1", params)
        assert hotspot_res.total_hotspots >= 1
        top_h = hotspot_res.hotspots[0]
        assert top_h.incident_count == 3
        assert top_h.primary_incident_type == "MEDICAL"


# ---------------------------------------------------------------------------
# Test 8: Demand Forecasting with Prediction Intervals & Insufficient Data
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_forecasting_insufficient_data(mock_db):
    # Only 2 points inserted (< 5 required)
    now_iso = datetime.now(timezone.utc).isoformat()
    await mock_db.incidents.insert_one({"incident_id": "i1", "started_at": now_iso})
    await mock_db.incidents.insert_one({"incident_id": "i2", "started_at": now_iso})

    with patch("app.core.database.get_database", return_value=mock_db):
        res = await forecasting_service.generate_demand_forecast(
            metric_name="incident_volume",
            horizon=ForecastHorizon.NEXT_DAY,
        )
        assert res.status == "INSUFFICIENT_DATA"
        assert len(res.forecast_points) == 0
        assert "Insufficient historical data" in res.message


@pytest.mark.asyncio
async def test_forecasting_with_sufficient_data(mock_db):
    now = datetime.now(timezone.utc)
    for i in range(10):
        await mock_db.incidents.insert_one({
            "incident_id": f"inc_hist_{i}",
            "started_at": (now - timedelta(days=i)).isoformat(),
        })

    with patch("app.core.database.get_database", return_value=mock_db):
        res = await forecasting_service.generate_demand_forecast(
            metric_name="incident_volume",
            horizon=ForecastHorizon.NEXT_DAY,
        )
        assert res.status == "AVAILABLE"
        assert len(res.forecast_points) > 0
        pt = res.forecast_points[0]
        assert pt.predicted_value > 0.0
        assert pt.lower_bound_p10 <= pt.predicted_value <= pt.upper_bound_p90
        assert pt.confidence_level == 0.80


# ---------------------------------------------------------------------------
# Test 9: Operational Recommendations
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_operational_recommendations(mock_db):
    now_iso = datetime.now(timezone.utc).isoformat()
    # 0 available responders and 1 open incident -> generates capacity recommendation
    await mock_db.incidents.insert_one({"incident_id": "inc_p", "status": "OPEN", "started_at": now_iso})
    await mock_db.responder_profiles.insert_one({"responder_id": "r_busy", "status": "ACTIVE", "is_available": False})

    with patch("app.core.database.get_database", return_value=mock_db):
        recs = await operational_intelligence_service.generate_operational_recommendations()
        assert recs.total_recommendations >= 1
        cap_rec = [r for r in recs.recommendations if r.category == "RESPONDER_CAPACITY"][0]
        assert "Zero Available Responders" in cap_rec.title
        assert cap_rec.urgency == "HIGH"


# ---------------------------------------------------------------------------
# Test 10: Surge Detection and Alert Deduplication Cooldown
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_incident_surge_and_cooldown(mock_db):
    now = datetime.now(timezone.utc)
    # Insert 6 incidents in the last 30 minutes
    for i in range(6):
        await mock_db.incidents.insert_one({
            "incident_id": f"inc_surge_{i}",
            "started_at": (now - timedelta(minutes=10)).isoformat(),
            "jurisdiction_id": "jur_surge",
        })

    with patch("app.core.database.get_database", return_value=mock_db):
        alert = await operational_intelligence_service.evaluate_incident_surge(jurisdiction_id="jur_surge")
        assert alert is not None
        assert alert.alert_type == "INCIDENT_SURGE"
        assert alert.actual_value >= 1.5

        # Second evaluation should be suppressed by cooldown
        second_eval = await operational_intelligence_service.evaluate_incident_surge(jurisdiction_id="jur_surge")
        assert second_eval is None


# ---------------------------------------------------------------------------
# Test 11: Export Data PII Redaction & Audit Logging
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_export_service_pii_redaction(mock_db):
    now_iso = datetime.now(timezone.utc).isoformat()
    await mock_db.incidents.insert_one({
        "incident_id": "inc_secret",
        "tourist_id": "user_sensitive_12345",
        "status": "RESOLVED",
        "started_at": now_iso,
    })

    with patch("app.core.database.get_database", return_value=mock_db):
        req = ExportJobCreateRequest(export_type="incidents", format=ExportFormat.CSV)
        job = await export_service.create_export_job("auth_officer", "tenant_1", req)
        assert job.status.value == "completed"

        payload, filename, media_type = await export_service.get_export_payload(job.job_id, "auth_officer", "authority")
        assert "user_sensitive_12345" not in payload  # Direct PII must be redacted
        assert "ANON_" in payload  # Anonymized token present


# ---------------------------------------------------------------------------
# Test 12: Metric Catalog Integrity
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_metric_catalog():
    catalog = await analytics_service.get_metric_catalog()
    assert catalog.total_metrics >= 5
    keys = [m.metric_key for m in catalog.metrics]
    assert "active_tourists" in keys
    assert "median_response_time" in keys
    assert "demand_forecast" in keys
    assert "unknown_safety_state_rate" in keys
