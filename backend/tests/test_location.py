import asyncio
import copy
import json
import pytest
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

sys.path.insert(0, "backend")

from fastapi.testclient import TestClient
from app.main import app
import app.core.database as db_module
import app.routers.auth as auth_router_mod
import app.routers.location as location_router_mod
import app.services.location_service as location_service_mod
from app.core.security import create_access_token
from app.schemas.location import (
    LocationSampleCreate,
    LocationStaleness,
    TrackingSessionStatus,
)
from app.services.location_service import (
    calculate_staleness,
    location_service,
    REDIS_LIVE_TTL_SECONDS,
    _memory_live_store,
)


# In-memory mock collection for async testing
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

    async def update_one(self, filter_dict, update_dict, upsert=False, *args, **kwargs):
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                if "$set" in update_dict:
                    doc.update(copy.deepcopy(update_dict["$set"]))
                if "$inc" in update_dict:
                    for ik, iv in update_dict["$inc"].items():
                        doc[ik] = doc.get(ik, 0) + iv
                return type("Obj", (), {"modified_count": 1, "matched_count": 1})()
        if upsert:
            new_doc = copy.deepcopy(filter_dict)
            if "$setOnInsert" in update_dict:
                new_doc.update(copy.deepcopy(update_dict["$setOnInsert"]))
            if "$set" in update_dict:
                new_doc.update(copy.deepcopy(update_dict["$set"]))
            if "$inc" in update_dict:
                for ik, iv in update_dict["$inc"].items():
                    new_doc[ik] = iv
            self.docs.append(new_doc)
            return type("Obj", (), {"modified_count": 0, "matched_count": 0, "upserted_id": new_doc.get("id", "new")})()
        return type("Obj", (), {"modified_count": 0, "matched_count": 0})()

    async def find_one_and_update(self, filter_dict, update_dict, *args, **kwargs):
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                if "$set" in update_dict:
                    doc.update(copy.deepcopy(update_dict["$set"]))
                return copy.deepcopy(doc)
        return None

    async def count_documents(self, filter_dict=None):
        filter_dict = filter_dict or {}
        return sum(1 for doc in self.docs if self._matches(doc, filter_dict))

    async def create_index(self, *args, **kwargs):
        return "index_created"


class MockAppDatabase:
    def __init__(self):
        self.location_history = MockMongoCollection("location_history")
        self.tracking_sessions = MockMongoCollection("tracking_sessions")
        self.tourist_profiles = MockMongoCollection("tourist_profiles")
        self.tourists = MockMongoCollection("tourists")
        self.authority = MockMongoCollection("authority")
        self.users = MockMongoCollection("users")
        self.zones = MockMongoCollection("zones")
        self.zone_transitions = MockMongoCollection("zone_transitions")

    def __getitem__(self, name):
        if not hasattr(self, name):
            setattr(self, name, MockMongoCollection(name))
        return getattr(self, name)

    def __getattr__(self, name):
        if name not in self.__dict__:
            self.__dict__[name] = MockMongoCollection(name)
        return self.__dict__[name]


@pytest.fixture(autouse=True)
def mock_db_fixture(monkeypatch):
    mock_db = MockAppDatabase()
    # Seed mock tourist user & profile
    mock_db.users.docs.append({
        "id": "tourist_user_1",
        "email": "tourist@toursafe.dev",
        "role": "tourist",
        "is_active": True,
    })
    mock_db.tourists.docs.append({
        "id": "tourist_user_1",
        "user_id": "tourist_user_1",
        "full_name": "Test Tourist",
        "email": "tourist@toursafe.dev",
    })
    mock_db.users.docs.append({
        "id": "auth_user_1",
        "email": "authority@toursafe.dev",
        "role": "authority",
        "is_active": True,
    })

    monkeypatch.setattr(db_module, "get_database", lambda: mock_db)
    monkeypatch.setattr(auth_router_mod, "get_database", lambda: mock_db)
    monkeypatch.setattr(location_service_mod, "get_database", lambda: mock_db)
    monkeypatch.setattr(location_router_mod, "get_database", lambda: mock_db)
    _memory_live_store.clear()
    return mock_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def tourist_auth_headers():
    token = create_access_token("tourist_user_1", "tourist")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def authority_auth_headers():
    token = create_access_token("auth_user_1", "authority")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers():
    token = create_access_token("admin_user_1", "admin")
    return {"Authorization": f"Bearer {token}"}


class TestLocationValidationAndSchemas:
    """Tests 1-8: Data model and coordinate validation."""

    def test_1_valid_location_creation(self):
        sample = LocationSampleCreate(
            session_id="sess_123456",
            timestamp=datetime.now(timezone.utc).isoformat(),
            latitude=10.2381123,
            longitude=77.4892456,
            altitude=2133.5,
            accuracy=4.2,
            speed=1.5,
            heading=180.0,
            sequence_number=1,
        )
        assert sample.latitude == 10.2381123
        assert sample.longitude == 77.4892456
        assert sample.sequence_number == 1

    def test_2_invalid_latitude_rejected(self):
        with pytest.raises(ValueError):
            LocationSampleCreate(
                session_id="sess_1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                latitude=91.5,  # > 90
                longitude=77.48,
                sequence_number=1,
            )
        with pytest.raises(ValueError):
            LocationSampleCreate(
                session_id="sess_1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                latitude=-90.1,  # < -90
                longitude=77.48,
                sequence_number=1,
            )

    def test_3_invalid_longitude_rejected(self):
        with pytest.raises(ValueError):
            LocationSampleCreate(
                session_id="sess_1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                latitude=10.23,
                longitude=180.5,  # > 180
                sequence_number=1,
            )
        with pytest.raises(ValueError):
            LocationSampleCreate(
                session_id="sess_1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                latitude=10.23,
                longitude=-181.0,  # < -180
                sequence_number=1,
            )

    def test_4_invalid_accuracy_rejected(self):
        with pytest.raises(ValueError):
            LocationSampleCreate(
                session_id="sess_1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                latitude=10.23,
                longitude=77.48,
                accuracy=-5.0,  # Negative
                sequence_number=1,
            )

    def test_5_invalid_speed_rejected(self):
        with pytest.raises(ValueError):
            LocationSampleCreate(
                session_id="sess_1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                latitude=10.23,
                longitude=77.48,
                speed=-1.0,  # Negative
                sequence_number=1,
            )

    def test_6_invalid_heading_rejected(self):
        with pytest.raises(ValueError):
            LocationSampleCreate(
                session_id="sess_1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                latitude=10.23,
                longitude=77.48,
                heading=365.0,  # > 360
                sequence_number=1,
            )
        with pytest.raises(ValueError):
            LocationSampleCreate(
                session_id="sess_1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                latitude=10.23,
                longitude=77.48,
                heading=-10.0,  # < 0
                sequence_number=1,
            )

    def test_7_invalid_timestamp_rejected(self):
        with pytest.raises(ValueError):
            LocationSampleCreate(
                session_id="sess_1",
                timestamp="invalid-date-string",
                latitude=10.23,
                longitude=77.48,
                sequence_number=1,
            )
        # Extreme future timestamp
        future_ts = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        with pytest.raises(ValueError):
            LocationSampleCreate(
                session_id="sess_1",
                timestamp=future_ts,
                latitude=10.23,
                longitude=77.48,
                sequence_number=1,
            )

    def test_8_sequence_number_validation(self):
        with pytest.raises(ValueError):
            LocationSampleCreate(
                session_id="sess_1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                latitude=10.23,
                longitude=77.48,
                sequence_number=0,  # Must be >= 1
            )


class TestLocationStalenessCalculations:
    """Test 16: Staleness states (LIVE, RECENT, STALE, UNKNOWN)."""

    def test_16_staleness_calculation_live(self):
        # 5 seconds ago -> LIVE
        ts = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        state, age = calculate_staleness(ts)
        assert state == LocationStaleness.LIVE
        assert age is not None and age <= 15.0

    def test_16_staleness_calculation_recent(self):
        # 30 seconds ago -> RECENT
        ts = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        state, age = calculate_staleness(ts)
        assert state == LocationStaleness.RECENT

    def test_16_staleness_calculation_stale(self):
        # 120 seconds ago -> STALE
        ts = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        state, age = calculate_staleness(ts)
        assert state == LocationStaleness.STALE

    def test_16_staleness_calculation_unknown(self):
        # 400 seconds ago -> UNKNOWN
        ts = (datetime.now(timezone.utc) - timedelta(seconds=400)).isoformat()
        state, age = calculate_staleness(ts)
        assert state == LocationStaleness.UNKNOWN

        # Missing / None
        state_none, age_none = calculate_staleness(None)
        assert state_none == LocationStaleness.UNKNOWN
        assert age_none is None


class TestLocationAPIEndpoints:
    """Tests 9-15, 17-20: API, security, authorization, history & pagination."""

    def test_9_unauthorized_location_update_rejected(self, client):
        payload = {
            "session_id": "sess_001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latitude": 10.2381,
            "longitude": 77.4892,
            "sequence_number": 1,
        }
        res = client.post("/api/v1/location/update", json=payload)
        assert res.status_code == 401

    def test_10_tourist_identity_derived_from_token(self, client, tourist_auth_headers):
        payload = {
            "session_id": "sess_001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latitude": 10.2381,
            "longitude": 77.4892,
            "accuracy": 5.0,
            "speed": 1.2,
            "heading": 45.0,
            "sequence_number": 1,
        }
        res = client.post("/api/v1/location/update", json=payload, headers=tourist_auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["tourist_id"] == "tourist_user_1"
        assert data["latitude"] == 10.2381
        assert data["longitude"] == 77.4892
        assert data["sequence_number"] == 1

    def test_11_redis_live_location_and_current_endpoint(self, client, tourist_auth_headers):
        # Post fresh location
        now_ts = datetime.now(timezone.utc).isoformat()
        payload = {
            "session_id": "sess_live_test",
            "timestamp": now_ts,
            "latitude": 10.2400,
            "longitude": 77.4900,
            "accuracy": 3.5,
            "sequence_number": 2,
        }
        post_res = client.post("/api/v1/location/update", json=payload, headers=tourist_auth_headers)
        assert post_res.status_code == 201

        # Read back from /tourists/me/location
        get_res = client.get("/api/v1/tourists/me/location", headers=tourist_auth_headers)
        assert get_res.status_code == 200
        live = get_res.json()
        assert live["tourist_id"] == "tourist_user_1"
        assert live["location"]["latitude"] == 10.2400
        assert live["location"]["longitude"] == 77.4900
        assert live["staleness"] == LocationStaleness.LIVE.value

    @pytest.mark.asyncio
    async def test_12_redis_ttl_fallback(self):
        # Simulate expired entry in cache
        import time
        _memory_live_store["expired_tourist"] = (
            {
                "latitude": 10.20,
                "longitude": 77.40,
                "timestamp": (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat(),
            },
            time.time() - 10,  # Expired in the past
        )
        # Checking expired key should pop and return fallback
        live = await location_service.get_live_location("expired_tourist")
        assert live.staleness in (LocationStaleness.UNKNOWN, LocationStaleness.STALE)

    def test_13_15_20_location_history_and_pagination(self, client, tourist_auth_headers):
        # Post 3 locations
        for i in range(1, 4):
            ts = (datetime.now(timezone.utc) - timedelta(minutes=10 - i)).isoformat()
            client.post(
                "/api/v1/location/update",
                json={
                    "session_id": "sess_hist",
                    "timestamp": ts,
                    "latitude": 10.2380 + (i * 0.001),
                    "longitude": 77.4890 + (i * 0.001),
                    "sequence_number": i,
                },
                headers=tourist_auth_headers,
            )

        # Get history with limit=2
        res = client.get(
            "/api/v1/tourists/me/location-history?limit=2&skip=0",
            headers=tourist_auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["tourist_id"] == "tourist_user_1"
        assert len(data["items"]) <= 2
        assert data["limit"] == 2
        assert data["skip"] == 0

    def test_17_tracking_session_lifecycle(self, client, tourist_auth_headers):
        # Start session
        start_res = client.post(
            "/api/v1/location/session/start",
            json={"device_id": "android_pixel_8"},
            headers=tourist_auth_headers,
        )
        assert start_res.status_code == 200
        start_data = start_res.json()
        session_id = start_data["session_id"]
        assert start_data["status"] == "active"

        # Stop session
        stop_res = client.post(
            "/api/v1/location/session/stop",
            json={"session_id": session_id},
            headers=tourist_auth_headers,
        )
        assert stop_res.status_code == 200
        stop_data = stop_res.json()
        assert stop_data["status"] == "stopped"

    def test_18_authority_location_access(self, client, authority_auth_headers, tourist_auth_headers):
        # First ensure tourist has a location
        client.post(
            "/api/v1/location/update",
            json={
                "session_id": "sess_auth_view",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latitude": 10.2395,
                "longitude": 77.4895,
                "sequence_number": 10,
            },
            headers=tourist_auth_headers,
        )

        # Authority inspects tourist live location
        auth_res = client.get(
            "/api/v1/authority/tourists/tourist_user_1/location",
            headers=authority_auth_headers,
        )
        assert auth_res.status_code == 200
        data = auth_res.json()
        assert data["tourist_id"] == "tourist_user_1"
        assert data["location"]["latitude"] == 10.2395

        # Authority inspects tourist history
        hist_res = client.get(
            "/api/v1/authority/tourists/tourist_user_1/location-history?limit=10",
            headers=authority_auth_headers,
        )
        assert hist_res.status_code == 200
        hist_data = hist_res.json()
        assert hist_data["tourist_id"] == "tourist_user_1"

        # Authority gets all live locations
        live_list_res = client.get(
            "/api/v1/authority/live-locations",
            headers=authority_auth_headers,
        )
        assert live_list_res.status_code == 200
        assert isinstance(live_list_res.json(), list)

    def test_19_tourist_cannot_access_authority_location_endpoint(self, client, tourist_auth_headers):
        res = client.get(
            "/api/v1/authority/tourists/other_tourist_99/location",
            headers=tourist_auth_headers,
        )
        assert res.status_code == 403

        res_hist = client.get(
            "/api/v1/authority/tourists/other_tourist_99/location-history",
            headers=tourist_auth_headers,
        )
        assert res_hist.status_code == 403

        res_all = client.get(
            "/api/v1/authority/live-locations",
            headers=tourist_auth_headers,
        )
        assert res_all.status_code == 403
