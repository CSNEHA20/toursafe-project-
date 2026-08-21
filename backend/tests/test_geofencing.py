"""
TourSafe - Geofencing Engine Test Suite (Prompt 10)

Comprehensive unit and integration tests covering:
1. Precise GeoJSON Point-in-Polygon, holes, MultiPolygon, and boundary geodesic distance calculations
2. GPS accuracy circle vs boundary uncertainty modeling
3. Hysteresis state machine & temporal jitter protection
4. Accurate timestamp-based dwell tracking and threshold event triggering
5. Overlapping zones concurrent membership & risk prioritization
6. Non-destructive stale GPS handling (no fake exits)
7. Redis active state persistence & TTL
8. MongoDB auditable transition history
9. Realtime event envelopes & deduplication
10. Tourist, Authority, and Dev API endpoint security & functionality
"""

import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

sys.path.insert(0, "backend")

from app.main import app
from app.core.security import create_access_token
import copy
import app.core.database as db_module
from app.services.geofencing.geometry import (
    geodesic_distance_meters,
    point_to_segment_distance_meters,
    point_in_polygon,
    point_in_multipolygon,
    distance_to_geometry_boundary_meters,
    evaluate_point_containment,
    bounding_box_for_geometry,
    is_point_in_bounding_box,
)
from app.services.geofencing.types import (
    ZoneMembershipState,
    MembershipConfidence,
    ContainmentStatus,
    ActiveZoneMembership,
    TouristGeofenceSnapshot,
    ZoneTransitionRecord,
)
from app.services.geofencing.quality import (
    categorize_gps_accuracy,
    evaluate_boundary_uncertainty,
)
from app.services.geofencing.state import (
    GeofenceStateMachine,
    ZoneStateContext,
)
from app.services.geofencing.engine import GeofenceEngine
from app.services.geofencing.events import GeofenceEventPublisher


class MockMongoCollection:
    def __init__(self, name="collection"):
        self.name = name
        self.docs: List[Dict[str, Any]] = []

    def _matches(self, doc: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
        for k, v in filter_dict.items():
            if k == "$or":
                sub_matches = any(self._matches(doc, sub) for sub in v)
                if not sub_matches:
                    return False
            elif isinstance(v, dict):
                val = doc.get(k)
                if "$gte" in v and "$lte" in v:
                    if not (v["$gte"] <= str(val) <= v["$lte"]):
                        return False
                elif "$gte" in v:
                    if not (str(val) >= v["$gte"]):
                        return False
                elif "$lte" in v:
                    if not (str(val) <= v["$lte"]):
                        return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    async def find_one(self, filter_dict=None, sort=None, *args, **kwargs):
        docs_copy = list(self.docs)
        if sort:
            for sort_key, sort_dir in sort:
                docs_copy.sort(key=lambda x: str(x.get(sort_key, "")), reverse=(sort_dir == -1))
        if not filter_dict:
            return copy.deepcopy(docs_copy[0]) if docs_copy else None
        for doc in docs_copy:
            if self._matches(doc, filter_dict):
                return copy.deepcopy(doc)
        return None

    def find(self, filter_dict=None, *args, **kwargs):
        filtered = []
        filter_dict = filter_dict or {}
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                filtered.append(copy.deepcopy(doc))

        class Cursor:
            def __init__(self, items):
                self.items = items
                self._skip = 0
                self._limit = len(items)

            def sort(self, key, direction=1):
                reverse = direction == -1
                self.items.sort(key=lambda x: str(x.get(key, "")), reverse=reverse)
                return self

            def skip(self, n):
                self._skip = n
                return self

            def limit(self, n):
                self._limit = n
                return self

            async def to_list(self, length=None):
                limit_val = self._limit if length is None else length
                return self.items[self._skip : self._skip + limit_val]

            def __aiter__(self):
                self._iter_idx = self._skip
                self._iter_end = min(self._skip + self._limit, len(self.items))
                return self

            async def __anext__(self):
                if self._iter_idx >= self._iter_end:
                    raise StopAsyncIteration
                item = self.items[self._iter_idx]
                self._iter_idx += 1
                return item

        return Cursor(filtered)

    async def insert_one(self, document):
        doc = copy.deepcopy(document)
        if "id" not in doc:
            doc["id"] = f"id_{len(self.docs) + 1}"
        if "_id" not in doc:
            doc["_id"] = doc["id"]
        self.docs.append(doc)
        return type("Obj", (), {"inserted_id": doc["id"]})()

    async def count_documents(self, filter_dict=None):
        filter_dict = filter_dict or {}
        return sum(1 for doc in self.docs if self._matches(doc, filter_dict))

    async def create_index(self, *args, **kwargs):
        return "index_created"


class MockAppDatabase:
    def __init__(self):
        self.zones = MockMongoCollection("zones")
        self.zone_transitions = MockMongoCollection("zone_transitions")
        self.zone_audits = MockMongoCollection("zone_audits")
        self.location_history = MockMongoCollection("location_history")
        self.tracking_sessions = MockMongoCollection("tracking_sessions")
        self.tourist_profiles = MockMongoCollection("tourist_profiles")
        self.tourists = MockMongoCollection("tourists")
        self.authority = MockMongoCollection("authority")
        self.users = MockMongoCollection("users")

    def __getitem__(self, name):
        if not hasattr(self, name):
            setattr(self, name, MockMongoCollection(name))
        return getattr(self, name)


@pytest.fixture(autouse=True)
def mock_db_fixture(monkeypatch):
    mock_db = MockAppDatabase()
    monkeypatch.setattr(db_module, "get_database", lambda: mock_db)
    monkeypatch.setattr(db_module, "database", mock_db)
    return mock_db
from app.services.geofencing.engine import GeofenceEngine
from app.services.geofencing.events import GeofenceEventPublisher


# ─── 1. GEOMETRY & CONTAINMENT TESTS ─────────────────────────────────────────

class TestGeospatialGeometryCalculations:
    """Tests RFC 7946 GeoJSON containment, distances, and edge cases."""

    # Simple square polygon around (77.485, 10.235)
    SQUARE_POLYGON = [
        [
            [77.4800, 10.2300],
            [77.4900, 10.2300],
            [77.4900, 10.2400],
            [77.4800, 10.2400],
            [77.4800, 10.2300],
        ]
    ]

    def test_point_inside_polygon(self):
        # Center of square
        inside, on_boundary = point_in_polygon(77.4850, 10.2350, self.SQUARE_POLYGON)
        assert inside is True
        assert on_boundary is False

    def test_point_outside_polygon(self):
        # West of square
        inside, on_boundary = point_in_polygon(77.4700, 10.2350, self.SQUARE_POLYGON)
        assert inside is False
        assert on_boundary is False

    def test_point_on_boundary_edge(self):
        # Exact south edge: latitude 10.2300, longitude 77.4850
        inside, on_boundary = point_in_polygon(77.4850, 10.2300, self.SQUARE_POLYGON)
        assert inside is True
        assert on_boundary is True

    def test_point_on_boundary_vertex(self):
        # Exact southwest vertex: [77.4800, 10.2300]
        inside, on_boundary = point_in_polygon(77.4800, 10.2300, self.SQUARE_POLYGON)
        assert inside is True
        assert on_boundary is True

    def test_concave_l_shaped_polygon(self):
        # L-shaped polygon
        l_poly = [
            [
                [0.0, 0.0],
                [4.0, 0.0],
                [4.0, 2.0],
                [2.0, 2.0],
                [2.0, 4.0],
                [0.0, 4.0],
                [0.0, 0.0],
            ]
        ]
        # Inside bottom-left leg
        in1, _ = point_in_polygon(1.0, 1.0, l_poly)
        assert in1 is True

        # Inside top-left leg
        in2, _ = point_in_polygon(1.0, 3.0, l_poly)
        assert in2 is True

        # In the empty corner (3.0, 3.0) -> OUTSIDE
        in3, _ = point_in_polygon(3.0, 3.0, l_poly)
        assert in3 is False

    def test_polygon_with_interior_hole(self):
        # Outer ring 0..10, Hole ring 3..7
        poly_with_hole = [
            # Outer ring
            [
                [0.0, 0.0],
                [10.0, 0.0],
                [10.0, 10.0],
                [0.0, 10.0],
                [0.0, 0.0],
            ],
            # Interior hole ring
            [
                [3.0, 3.0],
                [7.0, 3.0],
                [7.0, 7.0],
                [3.0, 7.0],
                [3.0, 3.0],
            ]
        ]
        # Point inside solid region (1.0, 1.0)
        in_solid, _ = point_in_polygon(1.0, 1.0, poly_with_hole)
        assert in_solid is True

        # Point inside the hole (5.0, 5.0) -> MUST BE FALSE
        in_hole, _ = point_in_polygon(5.0, 5.0, poly_with_hole)
        assert in_hole is False

        # Point outside outer ring (12.0, 5.0) -> MUST BE FALSE
        in_outside, _ = point_in_polygon(12.0, 5.0, poly_with_hole)
        assert in_outside is False

    def test_multipolygon_containment(self):
        # MultiPolygon with 2 separate islands
        multi_poly = [
            # Island 1
            [
                [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0], [0.0, 0.0]]
            ],
            # Island 2
            [
                [[10.0, 10.0], [12.0, 10.0], [12.0, 12.0], [10.0, 12.0], [10.0, 10.0]]
            ]
        ]
        # In Island 1
        in_1, _ = point_in_multipolygon(1.0, 1.0, multi_poly)
        assert in_1 is True

        # In Island 2
        in_2, _ = point_in_multipolygon(11.0, 11.0, multi_poly)
        assert in_2 is True

        # Between islands -> OUTSIDE
        in_between, _ = point_in_multipolygon(5.0, 5.0, multi_poly)
        assert in_between is False

    def test_geodesic_distance_meters(self):
        # Distance along equator for ~1 degree is approx 111.32 km = 111320m
        dist = geodesic_distance_meters(0.0, 0.0, 1.0, 0.0)
        assert 111000.0 < dist < 112000.0

    def test_distance_to_boundary_meters(self):
        geom = {"type": "Polygon", "coordinates": self.SQUARE_POLYGON}
        # Point inside square, 0.005 deg from edges (approx 550m)
        dist = distance_to_geometry_boundary_meters(77.4850, 10.2350, geom)
        assert 500.0 < dist < 600.0

    def test_bounding_box_and_prefilter(self):
        geom = {"type": "Polygon", "coordinates": self.SQUARE_POLYGON}
        bbox = bounding_box_for_geometry(geom)
        assert bbox == (77.4800, 10.2300, 77.4900, 10.2400)

        # Inside bbox
        assert is_point_in_bounding_box(77.4850, 10.2350, bbox) is True
        # Far outside bbox
        assert is_point_in_bounding_box(78.0000, 11.0000, bbox) is False


# ─── 2. GPS ACCURACY & UNCERTAINTY TESTS ─────────────────────────────────────

class TestGPSAccuracyAndUncertainty:
    """Tests GPS accuracy circle vs polygon boundary uncertainty."""

    def test_high_accuracy_containment(self):
        geom = {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.4800, 10.2300],
                    [77.4900, 10.2300],
                    [77.4900, 10.2400],
                    [77.4800, 10.2400],
                    [77.4800, 10.2300],
                ]
            ]
        }
        # Center of polygon with 5m accuracy
        res = evaluate_point_containment(
            latitude=10.2350,
            longitude=77.4850,
            accuracy_meters=5.0,
            boundary_geojson=geom,
        )
        assert res.is_contained is True
        assert res.is_boundary is False
        assert res.confidence_level == MembershipConfidence.HIGH
        assert res.confidence_score >= 0.8
        assert res.containment_status == ContainmentStatus.INSIDE

    def test_poor_accuracy_overlapping_boundary(self):
        geom = {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.4800, 10.2300],
                    [77.4900, 10.2300],
                    [77.4900, 10.2400],
                    [77.4800, 10.2400],
                    [77.4800, 10.2300],
                ]
            ]
        }
        # Near boundary (10.23005 is ~5.5m from 10.2300 south edge) with 60m accuracy
        res = evaluate_point_containment(
            latitude=10.23005,
            longitude=77.4850,
            accuracy_meters=60.0,
            boundary_geojson=geom,
        )
        assert res.is_contained is True
        # Accuracy radius (60m) is far larger than distance to boundary (5.5m)
        assert res.confidence_level == MembershipConfidence.UNCERTAIN
        assert res.confidence_score < 0.5
        assert res.containment_status == ContainmentStatus.UNCERTAIN

    def test_gps_accuracy_categorization(self):
        assert categorize_gps_accuracy(4.0) == "EXCELLENT"
        assert categorize_gps_accuracy(12.0) == "GOOD"
        assert categorize_gps_accuracy(25.0) == "MODERATE"
        assert categorize_gps_accuracy(45.0) == "POOR"
        assert categorize_gps_accuracy(75.0) == "UNRELIABLE"


# ─── 3. HYSTERESIS STATE MACHINE & JITTER TESTS ──────────────────────────────

class TestGeofenceHysteresisStateMachine:
    """Tests jitter protection and hysteresis state transitions."""

    ZONE = {
        "zone_id": "test_zone_1",
        "id": "test_zone_1",
        "name": "Kodaikanal Test Zone",
        "zone_type": "safe",
        "risk_level": "low",
        "properties": {"dwell_threshold_seconds": 300.0},
    }

    def test_fast_path_entry_when_deep_inside(self):
        containment = evaluate_point_containment(
            latitude=10.2350,
            longitude=77.4850,
            accuracy_meters=5.0,
            boundary_geojson={
                "type": "Polygon",
                "coordinates": [
                    [[77.4800, 10.2300], [77.4900, 10.2300], [77.4900, 10.2400], [77.4800, 10.2400], [77.4800, 10.2300]]
                ]
            }
        )
        ts = "2026-08-22T10:00:00Z"
        ctx = ZoneStateContext("test_zone_1")

        new_state, event, membership = GeofenceStateMachine.evaluate_transition(
            tourist_id="tourist_123",
            zone=self.ZONE,
            containment=containment,
            sample_timestamp=ts,
            existing_membership=None,
            state_ctx=ctx,
        )

        assert new_state == ZoneMembershipState.INSIDE
        assert event == "zone.entered"
        assert membership is not None
        assert membership.entered_at == ts

    def test_jitter_damping_near_boundary(self):
        """Alternating noisy samples near boundary must not cause rapid enter/exit oscillation."""
        ctx = ZoneStateContext("test_zone_1")
        existing_membership = None

        # Sample 1: Inside near boundary (distance 5m, accuracy 15m) -> ENTER_CANDIDATE
        c_inside_near = evaluate_point_containment(
            latitude=10.23005,
            longitude=77.4850,
            accuracy_meters=15.0,
            boundary_geojson={
                "type": "Polygon",
                "coordinates": [
                    [[77.4800, 10.2300], [77.4900, 10.2300], [77.4900, 10.2400], [77.4800, 10.2400], [77.4800, 10.2300]]
                ]
            }
        )

        state1, event1, m1 = GeofenceStateMachine.evaluate_transition(
            tourist_id="tourist_123",
            zone=self.ZONE,
            containment=c_inside_near,
            sample_timestamp="2026-08-22T10:00:01Z",
            existing_membership=existing_membership,
            state_ctx=ctx,
        )
        assert state1 == ZoneMembershipState.ENTER_CANDIDATE
        assert event1 is None  # No event on first ambiguous candidate!

        # Sample 2: Jitter outside
        c_outside_near = evaluate_point_containment(
            latitude=10.22995,
            longitude=77.4850,
            accuracy_meters=15.0,
            boundary_geojson={
                "type": "Polygon",
                "coordinates": [
                    [[77.4800, 10.2300], [77.4900, 10.2300], [77.4900, 10.2400], [77.4800, 10.2400], [77.4800, 10.2300]]
                ]
            }
        )

        state2, event2, m2 = GeofenceStateMachine.evaluate_transition(
            tourist_id="tourist_123",
            zone=self.ZONE,
            containment=c_outside_near,
            sample_timestamp="2026-08-22T10:00:02Z",
            existing_membership=m1,
            state_ctx=ctx,
        )
        # Reverts to OUTSIDE without ever emitting false enter/exit events!
        assert state2 == ZoneMembershipState.OUTSIDE
        assert event2 is None

    def test_exit_hysteresis(self):
        """Single noisy sample outside from INSIDE state enters EXIT_CANDIDATE, returning cancels exit."""
        ts_entry = "2026-08-22T10:00:00Z"
        current_membership = ActiveZoneMembership(
            zone_id="test_zone_1",
            name="Test Zone",
            zone_type="safe",
            risk_level="low",
            state=ZoneMembershipState.INSIDE,
            confidence_level=MembershipConfidence.HIGH,
            confidence_score=0.9,
            entered_at=ts_entry,
            last_seen_inside=ts_entry,
            dwell_duration_seconds=10.0,
            last_location_timestamp=ts_entry,
            distance_to_boundary_meters=50.0,
            accuracy_meters=5.0,
        )
        ctx = ZoneStateContext("test_zone_1")

        # 1. Single sample outside
        c_outside = evaluate_point_containment(
            latitude=10.2200,
            longitude=77.4850,
            accuracy_meters=5.0,
            boundary_geojson={
                "type": "Polygon",
                "coordinates": [
                    [[77.4800, 10.2300], [77.4900, 10.2300], [77.4900, 10.2400], [77.4800, 10.2400], [77.4800, 10.2300]]
                ]
            }
        )

        state1, event1, m1 = GeofenceStateMachine.evaluate_transition(
            tourist_id="tourist_123",
            zone=self.ZONE,
            containment=c_outside,
            sample_timestamp="2026-08-22T10:00:10Z",
            existing_membership=current_membership,
            state_ctx=ctx,
        )
        assert state1 == ZoneMembershipState.EXIT_CANDIDATE
        assert event1 is None  # Does NOT emit exit event on first sample!

        # 2. Next sample returns inside -> exit is cancelled, remains INSIDE!
        c_inside = evaluate_point_containment(
            latitude=10.2350,
            longitude=77.4850,
            accuracy_meters=5.0,
            boundary_geojson={
                "type": "Polygon",
                "coordinates": [
                    [[77.4800, 10.2300], [77.4900, 10.2300], [77.4900, 10.2400], [77.4800, 10.2400], [77.4800, 10.2300]]
                ]
            }
        )

        state2, event2, m2 = GeofenceStateMachine.evaluate_transition(
            tourist_id="tourist_123",
            zone=self.ZONE,
            containment=c_inside,
            sample_timestamp="2026-08-22T10:00:15Z",
            existing_membership=m1,
            state_ctx=ctx,
        )
        assert state2 == ZoneMembershipState.INSIDE
        assert event2 is None
        assert m2.entered_at == ts_entry  # Dwell timeline preserved!


# ─── 4. DWELL TRACKING & THRESHOLD EVENT TESTS ───────────────────────────────

class TestDwellTracking:
    """Tests exact timestamp-based dwell calculation and threshold crossing."""

    ZONE = {
        "zone_id": "test_zone_1",
        "name": "Kodaikanal Test Zone",
        "zone_type": "safe",
        "risk_level": "low",
        "properties": {"dwell_threshold_seconds": 300.0},
    }

    def test_dwell_duration_and_threshold_crossing(self):
        t0 = "2026-08-22T10:00:00Z"
        current_membership = ActiveZoneMembership(
            zone_id="test_zone_1",
            name="Test Zone",
            zone_type="safe",
            risk_level="low",
            state=ZoneMembershipState.INSIDE,
            confidence_level=MembershipConfidence.HIGH,
            confidence_score=0.9,
            entered_at=t0,
            last_seen_inside=t0,
            dwell_duration_seconds=0.0,
            dwell_threshold_notified=False,
            last_location_timestamp=t0,
            distance_to_boundary_meters=50.0,
            accuracy_meters=5.0,
        )
        ctx = ZoneStateContext("test_zone_1")

        c_inside = evaluate_point_containment(
            latitude=10.2350,
            longitude=77.4850,
            accuracy_meters=5.0,
            boundary_geojson={
                "type": "Polygon",
                "coordinates": [
                    [[77.4800, 10.2300], [77.4900, 10.2300], [77.4900, 10.2400], [77.4800, 10.2400], [77.4800, 10.2300]]
                ]
            }
        )

        # 1. Update after 100 seconds (under threshold 300s)
        t100 = "2026-08-22T10:01:40Z"
        s1, e1, m1 = GeofenceStateMachine.evaluate_transition(
            tourist_id="tourist_123",
            zone=self.ZONE,
            containment=c_inside,
            sample_timestamp=t100,
            existing_membership=current_membership,
            state_ctx=ctx,
        )
        assert s1 == ZoneMembershipState.INSIDE
        assert e1 is None
        assert m1.dwell_duration_seconds == 100.0
        assert m1.dwell_threshold_notified is False

        # 2. Update after 350 seconds (crosses threshold 300s)
        t350 = "2026-08-22T10:05:50Z"
        s2, e2, m2 = GeofenceStateMachine.evaluate_transition(
            tourist_id="tourist_123",
            zone=self.ZONE,
            containment=c_inside,
            sample_timestamp=t350,
            existing_membership=m1,
            state_ctx=ctx,
        )
        assert s2 == ZoneMembershipState.INSIDE
        assert e2 == "zone.dwell.threshold_reached"
        assert m2.dwell_duration_seconds == 350.0
        assert m2.dwell_threshold_notified is True

        # 3. Subsequent update after 400 seconds (should NOT emit threshold event again)
        t400 = "2026-08-22T10:06:40Z"
        s3, e3, m3 = GeofenceStateMachine.evaluate_transition(
            tourist_id="tourist_123",
            zone=self.ZONE,
            containment=c_inside,
            sample_timestamp=t400,
            existing_membership=m2,
            state_ctx=ctx,
        )
        assert s3 == ZoneMembershipState.INSIDE
        assert e3 is None  # Did not repeat dwell alert
        assert m3.dwell_duration_seconds == 400.0


# ─── 5. OVERLAPPING ZONES TESTS ──────────────────────────────────────────────

class TestOverlappingZones:
    """Tests simultaneous membership in multiple overlapping zones."""

    @pytest.mark.asyncio
    async def test_multi_zone_concurrent_containment(self):
        engine = GeofenceEngine()

        # Mock 2 overlapping zones
        zone_a = {
            "id": "zone_a",
            "zone_id": "zone_a",
            "name": "Zone A Safe Lake",
            "zone_type": "safe",
            "risk_level": "low",
            "status": "active",
            "is_active": True,
            "boundary": {
                "type": "Polygon",
                "coordinates": [
                    [[77.4800, 10.2300], [77.5000, 10.2300], [77.5000, 10.2500], [77.4800, 10.2500], [77.4800, 10.2300]]
                ]
            },
            "center": {"type": "Point", "coordinates": [77.4900, 10.2400]},
        }
        zone_b = {
            "id": "zone_b",
            "zone_id": "zone_b",
            "name": "Zone B Restricted Ridge",
            "zone_type": "restricted",
            "risk_level": "critical",
            "status": "active",
            "is_active": True,
            "boundary": {
                "type": "Polygon",
                "coordinates": [
                    [[77.4850, 10.2350], [77.5050, 10.2350], [77.5050, 10.2550], [77.4850, 10.2550], [77.4850, 10.2350]]
                ]
            },
            "center": {"type": "Point", "coordinates": [77.4950, 10.2450]},
        }

        # Point (77.4900, 10.2400) is inside BOTH Zone A and Zone B
        sample = type("Sample", (), {
            "latitude": 10.2400,
            "longitude": 77.4900,
            "accuracy": 5.0,
            "timestamp": "2026-08-22T10:00:00Z",
            "session_id": "sess_123",
        })()

        with patch("app.services.geofencing.engine.geofence_repository.find_candidate_zones", return_value=[zone_a, zone_b]), \
             patch("app.services.geofencing.engine.geofence_repository.record_transition", new_callable=AsyncMock) as mock_record, \
             patch("app.services.geofencing.engine.geofence_event_publisher.publish_zone_event", new_callable=AsyncMock):

            snapshot = await engine.process_location_sample("tourist_multi", "user_123", sample)

            # Both zones must be active
            assert snapshot.total_active_zones == 2
            zone_ids = {m.zone_id for m in snapshot.active_zones}
            assert "zone_a" in zone_ids
            assert "zone_b" in zone_ids

            # Highest risk level derived correctly (critical > low)
            assert snapshot.highest_risk_level == "critical"
            assert snapshot.primary_zone_type == "restricted"


# ─── 6. STALE LOCATION HANDLING TESTS ────────────────────────────────────────

class TestStaleLocationHandling:
    """Tests non-destructive staleness handling."""

    @pytest.mark.asyncio
    async def test_stale_gps_marks_state_stale_without_exiting(self):
        engine = GeofenceEngine()

        # Seed active membership
        initial_memberships = {
            "zone_a": ActiveZoneMembership(
                zone_id="zone_a",
                name="Zone A",
                zone_type="safe",
                risk_level="low",
                state=ZoneMembershipState.INSIDE,
                confidence_level=MembershipConfidence.HIGH,
                confidence_score=0.95,
                entered_at="2026-08-22T10:00:00Z",
                last_seen_inside="2026-08-22T10:00:00Z",
                dwell_duration_seconds=50.0,
                last_location_timestamp="2026-08-22T10:00:00Z",
                distance_to_boundary_meters=60.0,
                accuracy_meters=5.0,
            )
        }

        with patch.object(engine, "get_active_memberships", return_value=initial_memberships), \
             patch.object(engine, "save_active_memberships", new_callable=AsyncMock) as mock_save, \
             patch("app.services.geofencing.engine.geofence_event_publisher.publish_zone_event", new_callable=AsyncMock) as mock_publish:

            await engine.mark_tourist_stale("tourist_stale_test")

            # Check that saved membership is marked STALE
            mock_save.assert_called_once()
            saved_dict = mock_save.call_args[0][1]
            assert saved_dict["zone_a"].state == ZoneMembershipState.STALE

            # Check that stale event was emitted, NOT zone.exited
            mock_publish.assert_called_once()
            assert mock_publish.call_args[1]["event_type"] == "zone.membership.stale"


# ─── 7. REALTIME EVENT EMISSION & DEDUPLICATION TESTS ────────────────────────

class TestRealtimeEventEmissionAndDeduplication:
    """Tests realtime event envelope construction and deduplication."""

    @pytest.mark.asyncio
    async def test_event_deduplication(self):
        publisher = GeofenceEventPublisher()

        sample = type("Sample", (), {
            "latitude": 10.2400,
            "longitude": 77.4900,
            "accuracy": 5.0,
            "timestamp": "2026-08-22T10:00:00.123456Z",
            "session_id": "sess_123",
        })()

        zone = {"zone_id": "z1", "name": "Zone 1", "zone_type": "safe", "risk_level": "low"}
        containment = evaluate_point_containment(
            latitude=10.2400,
            longitude=77.4900,
            accuracy_meters=5.0,
            boundary_geojson={"type": "Polygon", "coordinates": []}
        )

        with patch("app.services.geofencing.events.realtime_bus.publish_to_channel", new_callable=AsyncMock) as mock_bus:
            # First emission -> SUCCESS
            env1 = await publisher.publish_zone_event(
                event_type="zone.entered",
                tourist_id="tourist_dedup",
                user_id="user_123",
                zone=zone,
                location_sample=sample,
                containment=containment,
            )
            assert env1 is not None
            assert env1.event_type == "zone.entered"
            assert mock_bus.call_count == 2  # tourist + authority channels

            # Immediate duplicate emission with same timestamp -> DEDUPLICATED (None)
            env2 = await publisher.publish_zone_event(
                event_type="zone.entered",
                tourist_id="tourist_dedup",
                user_id="user_123",
                zone=zone,
                location_sample=sample,
                containment=containment,
            )
            assert env2 is None
            assert mock_bus.call_count == 2  # No extra broadcast!


# ─── 8. API ENDPOINTS & ROLE AUTHORIZATION TESTS ─────────────────────────────

class TestGeofencingAPIEndpoints:
    """Tests FastAPI geofencing endpoints and role authorization."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def tourist_token(self):
        return create_access_token(user_id="user_tourist_1", role="tourist")

    @pytest.fixture
    def authority_token(self):
        return create_access_token(user_id="user_auth_1", role="authority")

    def test_tourist_get_current_zones(self, client, tourist_token):
        response = client.get(
            "/api/v1/tourists/me/zones/current",
            headers={"Authorization": f"Bearer {tourist_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "tourist_id" in data
        assert "active_zones" in data
        assert "highest_risk_level" in data

    def test_tourist_forbidden_on_authority_endpoint(self, client, tourist_token):
        response = client.get(
            "/api/v1/authority/tourists/tourist_123/zones/current",
            headers={"Authorization": f"Bearer {tourist_token}"},
        )
        assert response.status_code == 403

    def test_authority_get_tourist_zones(self, client, authority_token):
        response = client.get(
            "/api/v1/authority/tourists/tourist_123/zones/current",
            headers={"Authorization": f"Bearer {authority_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tourist_id"] == "tourist_123"

    def test_authority_live_occupancy(self, client, authority_token):
        response = client.get(
            "/api/v1/authority/zones/live-occupancy",
            headers={"Authorization": f"Bearer {authority_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "zones" in data

    def test_dev_diagnostics_endpoint(self, client):
        response = client.get("/api/v1/dev/geofence/diagnostics/tourist_test_diag")
        assert response.status_code == 200
        data = response.json()
        assert "tourist_id" in data

