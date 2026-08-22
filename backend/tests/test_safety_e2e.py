import sys
sys.path.insert(0, "backend")

import copy
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.security import create_access_token
import app.core.database as db_module
import app.services.safety.repository as safety_repo_mod
import app.services.location_service as location_service_mod
import app.routers.safety as safety_router_mod
import app.routers.tourists as tourist_router_mod
import app.routers.authority as auth_router_mod
import app.routers.auth as auth_mod
import app.services.geofencing.repository as geofence_repo_mod
from app.schemas.safety import SafetyState, IncidentStatus
from app.schemas.telemetry import TelemetryWindow, QualityMetrics
from app.services.geofencing import geofence_engine
from app.services.location_service import location_service
from app.services.ml.engine import ml_inference_engine
from app.services.safety import (
    SafetySignalFactory,
    safety_config,
    safety_orchestrator,
    safety_redis_state,
    safety_repository,
)


class MockMongoCollection:
    def __init__(self, name):
        self.name = name
        self.docs = []

    def _matches(self, doc, query):
        for k, v in query.items():
            if isinstance(v, dict) and "$in" in v:
                target_list = v["$in"]
                if doc.get(k) not in target_list:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    async def insert_one(self, doc):
        d = copy.deepcopy(doc)
        self.docs.append(d)
        return type("Obj", (), {"inserted_id": d.get("id", "new")})()

    async def find_one(self, filter_dict=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                return copy.deepcopy(doc)
        return None

    def find(self, filter_dict=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        matched = [copy.deepcopy(d) for d in self.docs if self._matches(d, filter_dict)]

        class Cursor:
            def __init__(self, items):
                self.items = items
            def sort(self, *args, **kwargs):
                return self
            def skip(self, n):
                self.items = self.items[n:]
                return self
            def limit(self, n):
                self.items = self.items[:n]
                return self
            def __aiter__(self):
                self._iter = iter(self.items)
                return self
            async def __anext__(self):
                try:
                    return next(self._iter)
                except StopIteration:
                    raise StopAsyncIteration
        return Cursor(matched)

    async def replace_one(self, filter_dict, new_doc, upsert=False, *args, **kwargs):
        for i, doc in enumerate(self.docs):
            if self._matches(doc, filter_dict):
                doc_copy = copy.deepcopy(new_doc)
                self.docs[i] = doc_copy
                return type("Obj", (), {"modified_count": 1, "matched_count": 1})()
        if upsert:
            self.docs.append(copy.deepcopy(new_doc))
            return type("Obj", (), {"modified_count": 0, "matched_count": 0, "upserted_id": new_doc.get("id", "new")})()
        return type("Obj", (), {"modified_count": 0, "matched_count": 0})()

    async def update_one(self, filter_dict, update_dict, upsert=False, *args, **kwargs):
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                if "$set" in update_dict:
                    doc.update(copy.deepcopy(update_dict["$set"]))
                return type("Obj", (), {"modified_count": 1, "matched_count": 1})()
        if upsert:
            new_doc = copy.deepcopy(filter_dict)
            if "$set" in update_dict:
                new_doc.update(copy.deepcopy(update_dict["$set"]))
            self.docs.append(new_doc)
            return type("Obj", (), {"modified_count": 0, "matched_count": 0, "upserted_id": new_doc.get("id", "new")})()
        return type("Obj", (), {"modified_count": 0, "matched_count": 0})()

    async def count_documents(self, filter_dict=None):
        filter_dict = filter_dict or {}
        return sum(1 for doc in self.docs if self._matches(doc, filter_dict))

    async def create_index(self, *args, **kwargs):
        return "index_created"


class MockAppDatabase:
    def __init__(self):
        self.safety_decisions = MockMongoCollection("safety_decisions")
        self.safety_incidents = MockMongoCollection("safety_incidents")
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
    # Seed mock user & tourist profile
    mock_db.users.docs.append({
        "id": "user_e2e_001",
        "email": "tourist_e2e@toursafe.dev",
        "role": "tourist",
        "is_active": True,
    })
    mock_db.tourists.docs.append({
        "id": "tourist_e2e_001",
        "user_id": "user_e2e_001",
        "full_name": "E2E Test Tourist",
        "email": "tourist_e2e@toursafe.dev",
        "is_active": True,
    })
    mock_db.users.docs.append({
        "id": "auth_officer_1",
        "email": "officer@toursafe.dev",
        "role": "authority",
        "is_active": True,
    })
    mock_db.authority.docs.append({
        "id": "auth_officer_1",
        "user_id": "auth_officer_1",
        "full_name": "Officer Smith",
        "role": "authority",
    })

    monkeypatch.setattr(db_module, "get_database", lambda: mock_db)
    monkeypatch.setattr(safety_repo_mod, "get_database", lambda: mock_db)
    monkeypatch.setattr(location_service_mod, "get_database", lambda: mock_db)
    monkeypatch.setattr(safety_router_mod, "get_database", lambda: mock_db)
    monkeypatch.setattr(tourist_router_mod, "get_database", lambda: mock_db)
    monkeypatch.setattr(auth_router_mod, "get_database", lambda: mock_db)
    monkeypatch.setattr(auth_mod, "get_database", lambda: mock_db)
    return mock_db


@pytest.mark.asyncio
class TestSafetyEndToEndPipeline:
    """Tests full pipeline from simulated multi-modal sensors to safety decisions & incidents."""

    async def test_end_to_end_safety_escalation_and_resolution(self):
        tourist_id = "tourist_e2e_001"
        user_id = "user_e2e_001"
        session_id = "sess_e2e_001"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Generate auth tokens (user_id, role)
        auth_token = create_access_token("auth_officer_1", "authority")
        tourist_token = create_access_token(user_id, "tourist")

        headers_auth = {"Authorization": f"Bearer {auth_token}"}
        headers_tourist = {"Authorization": f"Bearer {tourist_token}"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Initially check Tourist Safety Status -> UNKNOWN / Disconnected
            resp = await client.get("/api/v1/tourists/me/safety", headers=headers_tourist)
            assert resp.status_code == 200
            data = resp.json()
            assert "safety_status" in data

            # 2. Ingest Safe Location Sample
            from app.schemas.location import LocationSampleCreate
            loc_sample = LocationSampleCreate(
                latitude=15.2993,
                longitude=74.1240,
                accuracy=10.0,
                altitude=15.0,
                speed=1.2,
                heading=90.0,
                timestamp=now_iso,
                session_id=session_id,
                sequence_number=1,
            )
            await location_service.ingest_location(user_id=user_id, tourist_id=tourist_id, sample=loc_sample)

            # 3. Verify Authority Safety Status Endpoint -> NORMAL
            resp_auth = await client.get(f"/api/v1/authority/tourists/{tourist_id}/safety", headers=headers_auth)
            assert resp_auth.status_code == 200
            auth_data = resp_auth.json()
            assert auth_data["tourist_id"] == tourist_id
            assert auth_data["current_state"] == SafetyState.NORMAL.value
            assert auth_data["rule_version"] == "safety-rules-v1"

            # 4. Trigger Persistent Anomaly + Danger Zone (Escalation to INCIDENT_CANDIDATE & INCIDENT)
            anom_sig = SafetySignalFactory.create_anomaly_signal(
                tourist_id=tourist_id,
                session_id=session_id,
                state="anomalous",
                score=0.92,
                threshold=0.50,
                consecutive_windows=4,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            danger_sig = SafetySignalFactory.create_geofence_signal(
                tourist_id=tourist_id,
                session_id=session_id,
                zone_id="danger_glen_01",
                zone_name="Steep Ravine Danger Zone",
                zone_type="danger",
                risk_level="danger",
                membership_state="inside",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            # Ingest danger signals
            await safety_orchestrator.ingest_signal(danger_sig)
            dec_cand = await safety_orchestrator.ingest_signal(anom_sig)
            assert dec_cand.state == SafetyState.INCIDENT_CANDIDATE

            # Consecutive cycle in candidate confirms INCIDENT
            dec_inc = await safety_orchestrator.ingest_signal(anom_sig)
            assert dec_inc.state == SafetyState.INCIDENT

            # 5. Check Authority Active Incident Querying
            resp_inc = await client.get(f"/api/v1/authority/tourists/{tourist_id}/incidents", headers=headers_auth)
            assert resp_inc.status_code == 200
            inc_list = resp_inc.json()
            assert inc_list["total"] >= 1
            active_inc_id = inc_list["incidents"][0]["incident_id"]

            # 6. Acknowledge Incident by Authority
            resp_ack = await client.post(
                f"/api/v1/authority/incidents/{active_inc_id}/acknowledge",
                json={"notes": "Forward reconnaissance team dispatched"},
                headers=headers_auth,
            )
            assert resp_ack.status_code == 200
            assert resp_ack.json()["status"] == IncidentStatus.ACKNOWLEDGED.value

            # 7. Resolve Incident by Authority
            resp_res = await client.post(
                f"/api/v1/authority/incidents/{active_inc_id}/resolve",
                json={"resolution_reason": "Tourist verified safe at checkpoint Alpha"},
                headers=headers_auth,
            )
            assert resp_res.status_code == 200
            assert resp_res.json()["status"] == IncidentStatus.RESOLVED.value

            # 8. Query Decision History Audit Trail
            resp_hist = await client.get(f"/api/v1/authority/tourists/{tourist_id}/safety/history", headers=headers_auth)
            assert resp_hist.status_code == 200
            hist_data = resp_hist.json()
            assert hist_data["total"] >= 1
            assert len(hist_data["decisions"]) >= 1
            assert all("rule_version" in d for d in hist_data["decisions"])
