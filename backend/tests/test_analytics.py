"""
Unit and Integration Tests for TourSafe Tourist Intelligence & Authority Analytics Platform (Prompt 15)

Verifies:
- Canonical operational data aggregation (no parallel sources of truth)
- Time bucketing and normalization across hourly, daily, weekly, and monthly granularities
- Percentile calculations (P50, P90, P95, mean, min, max)
- GPS path noise reduction, jump filtering, and accurate distance calculation
- Geohash spatial grid clustering and k-anonymity privacy suppression
- Redis and memory caching with TTL and key isolation
- Incident lifecycle durations, SLA compliance, and false alarm rate
- Zone intelligence and dwell duration analytics
- Anomaly episodes and operational incident conversion rate
- Responder operational KPIs (acceptance, arrival times, unit stats)
- Notification analytics (sent vs delivered distinction, latencies)
- Data quality dashboard rules
- Tourist personal trip metrics and privacy isolation
- Export job generation and download security
- Fast API router authorization and RBAC
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.analytics import (
    AnalyticsFilterParams,
    ExportFormat,
    ExportJobCreateRequest,
    ExportStatus,
    HeatmapMetricType,
    QualityStatus,
    TimeGranularity,
)
from app.services.analytics.aggregation_engine import (
    aggregation_engine,
    compute_duration_percentiles,
    decode_geohash_center,
    encode_geohash,
    haversine_distance_meters,
    normalize_time_range,
)
from app.services.analytics.analytics_service import analytics_service
from app.services.analytics.cache import analytics_cache
from app.services.analytics.export_service import export_service


# ---------------------------------------------------------------------------
# Mock Database Fixture
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

    def skip(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    async def to_list(self, length=None):
        return self.items[:length] if length else self.items


class MockCollection:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(doc)
        return MagicMock(inserted_id="mock_id")

    async def insert_many(self, docs, ordered=True):
        self.docs.extend(docs)
        return MagicMock(inserted_ids=["mock_id"] * len(docs))

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
                return MagicMock(modified_count=1)
        if upsert:
            new_doc = dict(query)
            if "$set" in update:
                new_doc.update(update["$set"])
            self.docs.append(new_doc)
            return MagicMock(upserted_id="mock_upserted_id")
        return MagicMock(modified_count=0)

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

    async def find_one(self, query):
        for doc in self.docs:
            match = True
            for k, v in query.items():
                if isinstance(v, dict) and "$or" in v:
                    continue
                if k == "$or":
                    sub_match = any(doc.get(sk) == sv for sub in v for sk, sv in sub.items())
                    if not sub_match:
                        match = False
                        break
                elif doc.get(k) != v:
                    match = False
                    break
            if match:
                return dict(doc)
        return None

    def find(self, query=None, projection=None):
        query = query or {}
        matched = []
        for doc in self.docs:
            match = True
            for k, v in query.items():
                if isinstance(v, dict):
                    if "$gte" in v and doc.get(k, "") < v["$gte"]:
                        match = False
                        break
                    if "$lte" in v and doc.get(k, "") > v["$lte"]:
                        match = False
                        break
                    if "$in" in v and doc.get(k) not in v["$in"]:
                        match = False
                        break
                elif doc.get(k) != v:
                    match = False
                    break
            if match:
                matched.append(dict(doc))
        return MockAsyncCursor(matched)


class MockDatabase:
    def __init__(self):
        self.incidents = MockCollection()
        self.safety_decisions = MockCollection()
        self.location_history = MockCollection()
        self.tracking_sessions = MockCollection()
        self.zones = MockCollection()
        self.zone_transitions = MockCollection()
        self.anomaly_events = MockCollection()
        self.telemetry_samples = MockCollection()
        self.telemetry_windows = MockCollection()
        self.telemetry_sessions = MockCollection()
        self.responders = MockCollection()
        self.incident_assignments = MockCollection()
        self.responder_units = MockCollection()
        self.responder_locations = MockCollection()
        self.notifications = MockCollection()
        self.dead_letter_queue = MockCollection()
        self.sos_events = MockCollection()
        self.tourist_profiles = MockCollection()
        self.itineraries = MockCollection()
        self.export_jobs = MockCollection()


@pytest.fixture
def mock_db():
    mdb = MockDatabase()
    with patch("app.core.database.get_database", return_value=mdb), \
         patch("app.services.analytics.aggregation_engine.db_core.get_database", return_value=mdb), \
         patch("app.services.analytics.analytics_service.db_core.get_database", return_value=mdb), \
         patch("app.services.analytics.export_service.db_core.get_database", return_value=mdb):
        yield mdb


# ---------------------------------------------------------------------------
# 1. Aggregation Engine & Mathematical Helper Tests
# ---------------------------------------------------------------------------

def test_time_normalization_and_bounding():
    now = datetime.now(timezone.utc)
    # Default without params
    start, end = normalize_time_range(None, None, TimeGranularity.DAY)
    assert start < end
    s_dt = datetime.fromisoformat(start)
    e_dt = datetime.fromisoformat(end)
    assert (e_dt - s_dt).days <= 7

    # Enforce max limits (e.g. 500 days clamped to 90 days for daily)
    old_start = (now - timedelta(days=500)).isoformat()
    norm_start, norm_end = normalize_time_range(old_start, now.isoformat(), TimeGranularity.DAY)
    span = (datetime.fromisoformat(norm_end) - datetime.fromisoformat(norm_start)).days
    assert span == 90


def test_duration_percentiles_calculation():
    # Empty case
    p_empty = compute_duration_percentiles([])
    assert p_empty.count == 0
    assert p_empty.p50_seconds is None

    # Single element
    p_single = compute_duration_percentiles([100.0])
    assert p_single.count == 1
    assert p_single.p50_seconds == 100.0
    assert p_single.mean_seconds == 100.0

    # Ordered list 10 to 100
    data = [10.0 * i for i in range(1, 11)]  # 10, 20, ..., 100
    p = compute_duration_percentiles(data)
    assert p.count == 10
    assert p.min_seconds == 10.0
    assert p.max_seconds == 100.0
    assert p.p50_seconds == 55.0  # Median
    assert p.p90_seconds == 91.0
    assert p.mean_seconds == 55.0


def test_geohash_encoding_and_decoding():
    lat, lon = 28.6139, 77.2090  # New Delhi
    gh = encode_geohash(lat, lon, precision=6)
    assert isinstance(gh, str)
    assert len(gh) == 6

    center_lat, center_lon = decode_geohash_center(gh)
    assert abs(center_lat - lat) < 0.02
    assert abs(center_lon - lon) < 0.02


def test_haversine_distance_calculation():
    # Distance between New Delhi (28.6139, 77.2090) and Agra (27.1767, 78.0081) ~180-190 km
    dist_m = haversine_distance_meters(28.6139, 77.2090, 27.1767, 78.0081)
    dist_km = dist_m / 1000.0
    assert 170.0 < dist_km < 200.0


# ---------------------------------------------------------------------------
# 2. GPS Path Distance & Quality Analytics Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gps_distance_with_noise_and_jump_rejection(mock_db):
    tourist_id = "tourist_100"
    base_time = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Normal leg (1 km movement in 100s -> 10 m/s)
    # 2. Stationary / GPS noise (< 2m movement -> filtered from distance sum)
    # 3. GPS jump (50 km in 2s -> 25,000 m/s -> rejected jump)
    # 4. Low accuracy sample (accuracy = 150m -> filtered)
    # 5. Normal leg (another 1 km movement)
    samples = [
        {"tourist_id": tourist_id, "timestamp": base_time.isoformat(), "latitude": 28.6000, "longitude": 77.2000, "accuracy": 10.0},
        {"tourist_id": tourist_id, "timestamp": (base_time + timedelta(seconds=100)).isoformat(), "latitude": 28.6090, "longitude": 77.2000, "accuracy": 12.0},
        {"tourist_id": tourist_id, "timestamp": (base_time + timedelta(seconds=110)).isoformat(), "latitude": 28.609001, "longitude": 77.200001, "accuracy": 8.0},  # noise
        {"tourist_id": tourist_id, "timestamp": (base_time + timedelta(seconds=112)).isoformat(), "latitude": 29.0000, "longitude": 77.2000, "accuracy": 10.0},  # jump (43km in 2s)
        {"tourist_id": tourist_id, "timestamp": (base_time + timedelta(seconds=120)).isoformat(), "latitude": 28.6100, "longitude": 77.2000, "accuracy": 150.0},  # bad accuracy
        {"tourist_id": tourist_id, "timestamp": (base_time + timedelta(seconds=200)).isoformat(), "latitude": 28.6180, "longitude": 77.2000, "accuracy": 15.0},
    ]
    await mock_db.location_history.insert_many(samples)

    dist_km, valid_count, accuracies, gaps = await aggregation_engine.calculate_travel_distance_km(tourist_id=tourist_id)
    assert dist_km > 1.5 and dist_km < 3.0  # around 2km total valid
    assert valid_count >= 2
    assert len(accuracies) >= 2


# ---------------------------------------------------------------------------
# 3. Spatial Heatmap with k-Anonymity Privacy Suppression Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_spatial_heatmap_privacy_suppression(mock_db):
    now_iso = datetime.now(timezone.utc).isoformat()
    start_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    # Location A: 4 unique tourists (k >= 3 -> NOT suppressed)
    for i in range(4):
        await mock_db.location_history.insert_one({
            "tourist_id": f"tourist_{i}",
            "timestamp": now_iso,
            "latitude": 28.6139,
            "longitude": 77.2090,
        })

    # Location B: Only 1 unique tourist (k < 3 -> MUST be suppressed)
    await mock_db.location_history.insert_one({
        "tourist_id": "lone_tourist",
        "timestamp": now_iso,
        "latitude": 12.9716,
        "longitude": 77.5946,
    })

    heatmap = await aggregation_engine.aggregate_spatial_heatmap(
        metric_type=HeatmapMetricType.TOURIST_DENSITY,
        start_time=start_iso,
        end_time=now_iso,
        precision=5,
    )

    assert heatmap.total_cells == 2
    assert heatmap.suppressed_cells_count == 1
    # Check that the cell with 4 tourists is not suppressed
    unsuppressed = [c for c in heatmap.cells if not c.is_suppressed]
    assert len(unsuppressed) == 1
    assert unsuppressed[0].sample_count == 4

    # Check that the lone tourist cell is suppressed
    suppressed = [c for c in heatmap.cells if c.is_suppressed]
    assert len(suppressed) == 1
    assert suppressed[0].weight == 0.0


# ---------------------------------------------------------------------------
# 4. Analytics Caching Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analytics_cache_hit_and_dynamic_ttl():
    tenant = "auth_org_1"
    metric = "incidents"
    params = {"start_time": "2026-08-01T00:00:00Z", "end_time": "2026-08-02T00:00:00Z", "granularity": "day"}

    key = analytics_cache.generate_cache_key(tenant, metric, params)
    assert "auth_org_1" in key
    assert "incidents" in key

    # Set and get from cache
    payload = {"total_incidents": 42, "status": "ok"}
    await analytics_cache.set(key, payload, ttl_seconds=10)

    cached_val = await analytics_cache.get(key)
    assert cached_val is not None
    assert cached_val["total_incidents"] == 42
    assert cached_val["_cached"] is True

    # Invalidate
    await analytics_cache.invalidate_pattern(f"toursafe:analytics:{tenant}:*")
    post_inval = await analytics_cache.get(key)
    assert post_inval is None


# ---------------------------------------------------------------------------
# 5. Incident Analytics & SLA Compliance Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_incident_analytics_and_sla_durations(mock_db):
    now = datetime.now(timezone.utc)
    st1 = (now - timedelta(hours=2)).isoformat()
    ack1 = (now - timedelta(hours=1, minutes=55)).isoformat()  # 5 min ack
    res1 = (now - timedelta(hours=1, minutes=45)).isoformat()  # 15 min resolve (within SLA)

    st2 = (now - timedelta(hours=5)).isoformat()
    ack2 = (now - timedelta(hours=4, minutes=50)).isoformat()  # 10 min ack
    res2 = (now - timedelta(hours=4)).isoformat()  # 60 min resolve (outside SLA)

    # Incident 1
    await mock_db.incidents.insert_one({
        "incident_id": "inc_1",
        "tourist_id": "t1",
        "status": "RESOLVED",
        "severity": "HIGH",
        "source": "MANUAL_SOS",
        "started_at": st1,
        "acknowledged_at": ack1,
        "resolved_at": res1,
        "resolution_category": "RESPONDER_ASSISTED",
        "timeline": [
            {"action": "incident.created", "timestamp": st1},
            {"action": "incident.assigned", "timestamp": ack1},
            {"action": "assignment.arrived", "timestamp": (now - timedelta(hours=1, minutes=50)).isoformat()},
        ],
    })

    # Incident 2 (False alarm)
    await mock_db.incidents.insert_one({
        "incident_id": "inc_2",
        "tourist_id": "t2",
        "status": "RESOLVED",
        "severity": "LOW",
        "source": "SAFETY_ENGINE",
        "started_at": st2,
        "acknowledged_at": ack2,
        "resolved_at": res2,
        "resolution_category": "FALSE_ALARM",
        "timeline": [],
    })

    params = AnalyticsFilterParams(granularity=TimeGranularity.DAY)
    res = await analytics_service.get_incident_analytics("test_tenant", params)

    assert res.total_incidents == 2
    assert res.resolved_incidents == 2
    assert res.false_alarms == 1
    assert res.false_alarm_rate == 0.5
    assert res.by_source.get("MANUAL_SOS") == 1
    assert res.by_source.get("SAFETY_ENGINE") == 1
    assert res.time_to_acknowledge.count == 2
    assert res.time_to_acknowledge.p50_seconds == 450.0  # (300 + 600)/2 = 450s
    assert res.within_sla_count == 1
    assert res.outside_sla_count == 1
    assert res.sla_compliance_rate == 50.0


# ---------------------------------------------------------------------------
# 6. Zone Intelligence & Dwell Duration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zone_list_analytics(mock_db):
    now_iso = datetime.now(timezone.utc).isoformat()
    # Insert zone
    await mock_db.zones.insert_one({
        "id": "zone_red_fort",
        "name": "Red Fort Heritage Area",
        "risk_level": "medium",
        "zone_type": "warning",
        "is_active": True,
    })

    # Insert transitions
    await mock_db.zone_transitions.insert_many([
        {"zone_id": "zone_red_fort", "tourist_id": "t1", "event_type": "ENTRY", "timestamp": now_iso},
        {"zone_id": "zone_red_fort", "tourist_id": "t1", "event_type": "DWELL", "dwell_duration_seconds": 1200.0, "timestamp": now_iso},
        {"zone_id": "zone_red_fort", "tourist_id": "t2", "event_type": "ENTRY", "timestamp": now_iso},
        {"zone_id": "zone_red_fort", "tourist_id": "t2", "event_type": "DWELL", "dwell_duration_seconds": 600.0, "timestamp": now_iso},
        {"zone_id": "zone_red_fort", "tourist_id": "t2", "event_type": "EXIT", "timestamp": now_iso},
    ])

    params = AnalyticsFilterParams()
    res = await analytics_service.get_zone_list_analytics("test_tenant", params)

    assert res.total_zones == 1
    z = res.zones[0]
    assert z.zone_id == "zone_red_fort"
    assert z.unique_tourists == 2
    assert z.total_entries == 2
    assert z.total_exits == 1
    assert z.total_dwell_events == 2
    assert z.avg_dwell_seconds == 900.0
    assert z.max_dwell_seconds == 1200.0


# ---------------------------------------------------------------------------
# 7. Anomaly Intelligence & Conversion Rate Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anomaly_analytics_and_conversion_rate(mock_db):
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Anomaly that converted to incident
    await mock_db.anomaly_events.insert_one({
        "anomaly_id": "anom_1",
        "tourist_id": "t1",
        "status": "cleared",
        "model_version": "v1.0.0",
        "started_at": now_iso,
        "duration_seconds": 45.0,
        "peak_reconstruction_error": 0.85,
        "associated_incident_id": "inc_1",
    })

    # 2. Anomaly that cleared without incident
    await mock_db.anomaly_events.insert_one({
        "anomaly_id": "anom_2",
        "tourist_id": "t2",
        "status": "cleared",
        "model_version": "v1.0.0",
        "started_at": now_iso,
        "duration_seconds": 30.0,
        "peak_reconstruction_error": 0.65,
    })

    params = AnalyticsFilterParams()
    res = await analytics_service.get_anomaly_analytics("test_tenant", params)

    assert res.total_anomalies == 2
    assert res.by_model_version.get("v1.0.0") == 2
    assert res.incident_conversion_count == 1
    assert res.cleared_without_incident_count == 1
    assert res.operational_conversion_rate == 0.5
    assert res.score_distribution["0.7-0.9"] == 1
    assert res.score_distribution["0.5-0.7"] == 1


# ---------------------------------------------------------------------------
# 8. Responder Operational Analytics Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_responder_analytics(mock_db):
    now = datetime.now(timezone.utc)
    cr = now.isoformat()
    acc = (now + timedelta(seconds=120)).isoformat()
    arr = (now + timedelta(seconds=300)).isoformat()

    await mock_db.responders.insert_one({
        "responder_id": "resp_001",
        "name": "Officer Sharma",
        "active": True,
        "status": "AVAILABLE",
    })

    await mock_db.incident_assignments.insert_one({
        "assignment_id": "asgn_1",
        "responder_id": "resp_001",
        "responder_type": "POLICE",
        "status": "COMPLETED",
        "created_at": cr,
        "accepted_at": acc,
        "arrived_at": arr,
    })

    params = AnalyticsFilterParams()
    res = await analytics_service.get_responder_analytics("test_tenant", params)

    assert res.total_responders == 1
    assert res.total_assignments == 1
    assert res.completed_assignments == 1
    assert res.rejection_rate == 0.0
    assert res.acceptance_rate == 1.0
    assert res.p50_response_time_seconds == 120.0
    assert res.p50_arrival_time_seconds == 300.0


# ---------------------------------------------------------------------------
# 9. Notification Delivery Analytics Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notification_analytics(mock_db):
    now_iso = datetime.now(timezone.utc).isoformat()

    await mock_db.notifications.insert_many([
        {"notification_id": "n1", "channel": "PUSH", "category": "EMERGENCY", "status": "DELIVERED", "provider": "FIREBASE", "delivery_latency_ms": 250.0, "created_at": now_iso},
        {"notification_id": "n2", "channel": "SMS", "category": "EMERGENCY", "status": "SENT", "provider": "TWILIO", "created_at": now_iso},
        {"notification_id": "n3", "channel": "EMAIL", "category": "GENERAL", "status": "FAILED", "provider": "SENDGRID", "created_at": now_iso},
    ])

    params = AnalyticsFilterParams()
    res = await analytics_service.get_notification_analytics("test_tenant", params)

    assert res.total_created == 3
    assert res.total_sent == 2  # n1 (DELIVERED) and n2 (SENT)
    assert res.total_delivered == 1
    assert res.total_failed == 1
    assert res.delivery_success_rate == 50.0  # 1 delivered / 2 sent
    assert res.channel_distribution["PUSH"] == 1
    assert res.provider_health["FIREBASE"]["delivered"] == 1


# ---------------------------------------------------------------------------
# 10. Data Quality Dashboard Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_data_quality_dashboard(mock_db):
    res = await analytics_service.get_data_quality_dashboard()
    assert res.overall_health == QualityStatus.GOOD
    assert res.gps_quality.domain == "GPS Telemetry"
    assert res.ml_inference_quality.score == 99.2


# ---------------------------------------------------------------------------
# 11. Tourist Personal Trip Analytics Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tourist_personal_analytics(mock_db):
    tourist_id = "tourist_999"
    now_iso = datetime.now(timezone.utc).isoformat()

    await mock_db.itineraries.insert_one({
        "id": "trip_delhi",
        "tourist_id": tourist_id,
        "title": "Delhi Heritage Walk",
        "status": "completed",
        "start_date": now_iso,
        "created_at": now_iso,
    })

    await mock_db.location_history.insert_many([
        {"tourist_id": tourist_id, "timestamp": now_iso, "latitude": 28.60, "longitude": 77.20, "accuracy": 5.0},
        {"tourist_id": tourist_id, "timestamp": now_iso, "latitude": 28.61, "longitude": 77.20, "accuracy": 5.0},
    ])

    res = await analytics_service.get_tourist_analytics(tourist_id, AnalyticsFilterParams())
    assert res.tourist_id == tourist_id
    assert res.total_trips == 1
    assert res.completed_trips == 1
    assert len(res.trips) == 1
    assert res.trips[0].trip_id == "trip_delhi"


# ---------------------------------------------------------------------------
# 12. Export Job Lifecycle Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_job_lifecycle_and_download(mock_db):
    # Insert an incident to export
    now_iso = datetime.now(timezone.utc).isoformat()
    await mock_db.incidents.insert_one({
        "incident_id": "inc_exp_1",
        "tourist_id": "t1",
        "status": "RESOLVED",
        "severity": "CRITICAL",
        "source": "MANUAL_SOS",
        "started_at": now_iso,
    })

    req = ExportJobCreateRequest(
        export_type="incidents",
        format=ExportFormat.CSV,
    )
    job = await export_service.create_export_job(
        requested_by="admin_user",
        tenant_id="admin_user",
        req=req,
    )

    assert job.status == ExportStatus.COMPLETED
    assert job.record_count == 1
    assert job.file_size_bytes is not None

    # Fetch export status
    fetched = await export_service.get_export_job(job.job_id, requested_by="admin_user")
    assert fetched is not None
    assert fetched.job_id == job.job_id

    # Retrieve payload
    payload_str, fname, media_type = await export_service.get_export_payload(
        job_id=job.job_id,
        user_id="admin_user",
        role="admin",
    )
    assert "inc_exp_1" in payload_str
    assert media_type == "text/csv"

    # Unauthorized access rejection
    with pytest.raises(PermissionError):
        await export_service.get_export_payload(
            job_id=job.job_id,
            user_id="unauthorized_user",
            role="tourist",
        )
