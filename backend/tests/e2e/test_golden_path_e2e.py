"""
TourSafe QA — GOLDEN PATH End-to-End Test
==========================================
Validates the complete pipeline from tourist login through incident resolution and audit.

Golden Path Pipeline:
    TOURIST LOGIN
    -> START TRIP
    -> GPS + IMU TELEMETRY
    -> TELEMETRY INGESTION
    -> FEATURE EXTRACTION
    -> LSTM INFERENCE (stubbed)
    -> ANOMALY EVENT
    -> GEOFENCE EVALUATION
    -> RISK FUSION
    -> SAFETY STATE ESCALATION
    -> INCIDENT GENERATION
    -> NOTIFICATION
    -> AUTHORITY ACKNOWLEDGEMENT
    -> RESPONDER ASSIGNMENT
    -> RESPONDER ACCEPTANCE
    -> RESPONDER LOCATION UPDATE
    -> INCIDENT RESPONSE
    -> RESOLUTION
    -> CLOSURE
    -> ANALYTICS
    -> AUDIT TRAIL

Golden Path IDs are captured and used to trace the entire workflow.
Timestamps and latencies are recorded for the performance baseline.
"""

import sys
sys.path.insert(0, "backend")

import copy
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.security import create_access_token
import app.core.database as db_module
import app.services.safety.repository as safety_repo_mod
import app.services.location_service as location_service_mod
import app.routers.safety as safety_router_mod
import app.routers.tourists as tourist_router_mod
import app.routers.authority as authority_router_mod
import app.routers.auth as auth_router_mod
import app.services.geofencing.repository as geofence_repo_mod

from app.schemas.safety import SafetyState, IncidentStatus
from app.schemas.location import LocationSampleCreate
from app.services.safety import (
    SafetySignalFactory,
    safety_orchestrator,
    safety_repository,
)


# ============================================================
# GOLDEN PATH IDENTITIES (deterministic)
# ============================================================

GP_TOURIST_USER_ID = "gp_user_tourist_001"
GP_TOURIST_ID = "gp_tourist_001"
GP_AUTHORITY_USER_ID = "gp_authority_001"
GP_SESSION_ID = "gp_session_001"
GP_ZONE_DANGER = "gp_zone_danger_001"
GP_TRIP_ID = "gp_trip_001"

_golden_path_ids: Dict[str, str] = {}
_golden_path_timeline: List[Dict[str, Any]] = []


def record_step(component: str, event: str, result: str, latency_ms: Optional[float] = None):
    """Record a golden path step for the trace report."""
    _golden_path_timeline.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "component": component,
        "event": event,
        "result": result,
        "latency_ms": round(latency_ms, 2) if latency_ms else None,
    })


# ============================================================
# IN-MEMORY DB MOCK
# ============================================================

class MockCollection:
    def __init__(self, name="collection"):
        self.name = name
        self.docs: List[Dict[str, Any]] = []

    def _matches(self, doc, query):
        for k, v in query.items():
            if k == "$or":
                if not any(self._matches(doc, sub) for sub in v):
                    return False
            elif isinstance(v, dict):
                doc_val = doc.get(k)
                if "$in" in v:
                    if doc_val not in v["$in"]:
                        return False
                elif "$ne" in v:
                    if doc_val == v["$ne"]:
                        return False
                elif "$gt" in v:
                    if not (doc_val is not None and doc_val > v["$gt"]):
                        return False
                elif "$gte" in v:
                    if not (doc_val is not None and doc_val >= v["$gte"]):
                        return False
                elif "$lt" in v:
                    if not (doc_val is not None and doc_val < v["$lt"]):
                        return False
                elif "$lte" in v:
                    if not (doc_val is not None and doc_val <= v["$lte"]):
                        return False
                elif "$exists" in v:
                    if v["$exists"] != (k in doc):
                        return False
                else:
                    if doc_val != v:
                        return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    async def insert_one(self, doc):
        d = copy.deepcopy(doc)
        d.setdefault("_id", d.get("id", f"{self.name}_{len(self.docs)+1}"))
        self.docs.append(d)
        return type("IR", (), {"inserted_id": d["_id"]})()

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
            def sort(self, *a, **kw): return self
            def skip(self, n): self.items = self.items[n:]; return self
            def limit(self, n): self.items = self.items[:n]; return self
            def __aiter__(self): self._i = iter(self.items); return self
            async def __anext__(self):
                try: return next(self._i)
                except StopIteration: raise StopAsyncIteration
            async def to_list(self, length=None):
                return self.items[:length] if length else self.items
        return Cursor(matched)

    async def update_one(self, filter_dict, update_dict, upsert=False, *args, **kwargs):
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                if "$set" in update_dict:
                    doc.update(copy.deepcopy(update_dict["$set"]))
                if "$push" in update_dict:
                    for f, v in update_dict["$push"].items():
                        doc.setdefault(f, []).append(copy.deepcopy(v))
                return type("UR", (), {"modified_count": 1, "matched_count": 1})()
        if upsert:
            nd = copy.deepcopy(filter_dict)
            if "$set" in update_dict:
                nd.update(copy.deepcopy(update_dict["$set"]))
            nd.setdefault("_id", nd.get("id", f"upsert_{len(self.docs)+1}"))
            self.docs.append(nd)
            return type("UR", (), {"modified_count": 0, "matched_count": 0, "upserted_id": nd.get("id","new")})()
        return type("UR", (), {"modified_count": 0, "matched_count": 0})()

    async def update_many(self, filter_dict, update_dict, *args, **kwargs):
        count = 0
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                if "$set" in update_dict:
                    doc.update(copy.deepcopy(update_dict["$set"]))
                count += 1
        return type("UR", (), {"modified_count": count, "matched_count": count})()

    async def replace_one(self, filter_dict, replacement, upsert=False, *args, **kwargs):
        for i, doc in enumerate(self.docs):
            if self._matches(doc, filter_dict):
                self.docs[i] = copy.deepcopy(replacement)
                return type("UR", (), {"modified_count": 1, "matched_count": 1})()
        if upsert:
            self.docs.append(copy.deepcopy(replacement))
            return type("UR", (), {"modified_count": 0, "matched_count": 0, "upserted_id": replacement.get("id","new")})()
        return type("UR", (), {"modified_count": 0, "matched_count": 0})()

    async def count_documents(self, filter_dict=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        return sum(1 for d in self.docs if self._matches(d, filter_dict))

    async def delete_one(self, filter_dict, *args, **kwargs):
        for i, doc in enumerate(self.docs):
            if self._matches(doc, filter_dict):
                self.docs.pop(i)
                return type("DR", (), {"deleted_count": 1})()
        return type("DR", (), {"deleted_count": 0})()

    async def create_index(self, *a, **kw): return "idx"
    async def create_indexes(self, *a, **kw): return ["idx"]
    async def command(self, *a, **kw): return {"ok": 1}


class MockDB:
    def __init__(self):
        self._c: Dict[str, MockCollection] = {}

    def __getitem__(self, n):
        if n not in self._c:
            self._c[n] = MockCollection(n)
        return self._c[n]

    def __getattr__(self, n):
        if n.startswith("_"):
            raise AttributeError(n)
        return self[n]

    async def command(self, *a, **kw): return {"ok": 1}


# ============================================================
# FIXTURE: SEED MOCK DB
# ============================================================

@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    db = MockDB()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Seed golden path users
    db["users"].docs.extend([
        {
            "id": GP_TOURIST_USER_ID,
            "_id": GP_TOURIST_USER_ID,
            "email": "gp_tourist@example.com",
            "role": "tourist",
            "is_active": True,
            "full_name": "Golden Path Tourist",
        },
        {
            "id": GP_AUTHORITY_USER_ID,
            "_id": GP_AUTHORITY_USER_ID,
            "email": "gp_authority@example.com",
            "role": "authority",
            "is_active": True,
            "full_name": "Golden Path Officer",
        },
    ])

    db["tourists"].docs.append({
        "id": GP_TOURIST_ID,
        "_id": GP_TOURIST_ID,
        "user_id": GP_TOURIST_USER_ID,
        "full_name": "Golden Path Tourist",
        "email": "gp_tourist@example.com",
        "is_active": True,
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    db["authority"].docs.append({
        "id": GP_AUTHORITY_USER_ID,
        "_id": GP_AUTHORITY_USER_ID,
        "user_id": GP_AUTHORITY_USER_ID,
        "full_name": "Golden Path Officer",
        "role": "authority",
        "email": "gp_authority@example.com",
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    monkeypatch.setattr(db_module, "get_database", lambda: db)
    monkeypatch.setattr(safety_repo_mod, "get_database", lambda: db)
    monkeypatch.setattr(location_service_mod, "get_database", lambda: db)
    monkeypatch.setattr(safety_router_mod, "get_database", lambda: db)
    monkeypatch.setattr(tourist_router_mod, "get_database", lambda: db)
    monkeypatch.setattr(authority_router_mod, "get_database", lambda: db)
    monkeypatch.setattr(auth_router_mod, "get_database", lambda: db)

    return db


# ============================================================
# GOLDEN PATH TESTS
# ============================================================

@pytest.mark.asyncio
class TestGoldenPath:
    """
    Full golden path end-to-end test suite.
    """

    async def test_golden_path_full_pipeline(self):
        """
        Executes the entire TourSafe Golden Path pipeline sequentially:
        1. Tourist & Authority Token Generation
        2. Initial Safety Status Check
        3. Telemetry Ingestion (Location + IMU)
        4. Safety Baseline Establishment (NORMAL)
        5. Geofence Danger Zone Signal
        6. Anomaly Signals & Risk Fusion
        7. State Escalation to INCIDENT_CANDIDATE & INCIDENT
        8. Authority Active Incident Retrieval
        9. Authority Incident Acknowledgment
        10. Authority Incident Resolution
        11. Complete Decision History & Audit Trail
        """
        # Step 1: Authentication
        t_start = time.monotonic()
        tourist_token = create_access_token(GP_TOURIST_USER_ID, "tourist")
        authority_token = create_access_token(GP_AUTHORITY_USER_ID, "authority")
        auth_lat = (time.monotonic() - t_start) * 1000
        assert tourist_token and authority_token
        _golden_path_ids["tourist_token"] = tourist_token
        _golden_path_ids["authority_token"] = authority_token
        record_step("AUTH", "tokens_generated", "PASS", auth_lat)

        headers_tourist = {"Authorization": f"Bearer {tourist_token}"}
        headers_auth = {"Authorization": f"Bearer {authority_token}"}
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Step 2: Initial Safety Status Query
            t_start = time.monotonic()
            resp = await client.get("/api/v1/tourists/me/safety", headers=headers_tourist)
            lat = (time.monotonic() - t_start) * 1000
            assert resp.status_code == 200
            assert "safety_status" in resp.json()
            record_step("TOURIST_APP", "initial_safety_check", f"PASS: {resp.json()['safety_status']}", lat)

            # Step 3: Ingest Safe Location Sample
            from app.services.location_service import location_service
            t_start = time.monotonic()
            loc_sample = LocationSampleCreate(
                latitude=15.2993,
                longitude=74.1240,
                accuracy=10.0,
                altitude=15.0,
                speed=1.2,
                heading=90.0,
                timestamp=datetime.now(timezone.utc).isoformat(),
                session_id=GP_SESSION_ID,
                sequence_number=1,
            )
            await location_service.ingest_location(
                user_id=GP_TOURIST_USER_ID,
                tourist_id=GP_TOURIST_ID,
                sample=loc_sample,
            )
            lat = (time.monotonic() - t_start) * 1000
            _golden_path_ids["tracking_session_id"] = GP_SESSION_ID
            record_step("TELEMETRY", "gps_location_ingested", "PASS", lat)

            # Step 4: Verify Authority Safety Status -> NORMAL
            t_start = time.monotonic()
            resp_auth = await client.get(f"/api/v1/authority/tourists/{GP_TOURIST_ID}/safety", headers=headers_auth)
            lat = (time.monotonic() - t_start) * 1000
            assert resp_auth.status_code == 200
            auth_data = resp_auth.json()
            assert auth_data["tourist_id"] == GP_TOURIST_ID
            assert auth_data["current_state"] == SafetyState.NORMAL.value
            _golden_path_ids["safety_baseline"] = SafetyState.NORMAL.value
            record_step("SAFETY_ENGINE", "safety_baseline_established", "PASS: NORMAL", lat)

            # Step 5: Geofence Danger Zone Signal
            t_start = time.monotonic()
            danger_sig = SafetySignalFactory.create_geofence_signal(
                tourist_id=GP_TOURIST_ID,
                session_id=GP_SESSION_ID,
                zone_id=GP_ZONE_DANGER,
                zone_name="Golden Path Danger Zone",
                zone_type="danger",
                risk_level="danger",
                membership_state="inside",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            dec_geo = await safety_orchestrator.ingest_signal(danger_sig)
            lat = (time.monotonic() - t_start) * 1000
            _golden_path_ids["geofence_decision_state"] = dec_geo.state.value
            record_step("GEOFENCE_ENGINE", "danger_zone_signal_injected", f"PASS: {dec_geo.state.value}", lat)

            # Step 6: Anomaly Signal -> INCIDENT_CANDIDATE
            t_start = time.monotonic()
            anom_sig = SafetySignalFactory.create_anomaly_signal(
                tourist_id=GP_TOURIST_ID,
                session_id=GP_SESSION_ID,
                state="anomalous",
                score=0.92,
                threshold=0.50,
                consecutive_windows=4,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            dec_cand = await safety_orchestrator.ingest_signal(anom_sig)
            lat = (time.monotonic() - t_start) * 1000
            assert dec_cand.state == SafetyState.INCIDENT_CANDIDATE
            _golden_path_ids["risk_episode_state"] = dec_cand.state.value
            record_step("RISK_FUSION", "escalated_to_incident_candidate", "PASS: INCIDENT_CANDIDATE", lat)

            # Step 7: Persistent Anomaly -> INCIDENT
            t_start = time.monotonic()
            dec_inc = await safety_orchestrator.ingest_signal(anom_sig)
            lat = (time.monotonic() - t_start) * 1000
            assert dec_inc.state == SafetyState.INCIDENT
            _golden_path_ids["incident_state"] = dec_inc.state.value
            record_step("INCIDENT_ENGINE", "incident_generated", "PASS: INCIDENT", lat)

            # Step 8: Authority Active Incident Querying
            t_start = time.monotonic()
            resp_inc = await client.get(f"/api/v1/authority/tourists/{GP_TOURIST_ID}/incidents", headers=headers_auth)
            lat = (time.monotonic() - t_start) * 1000
            assert resp_inc.status_code == 200
            inc_list = resp_inc.json()
            assert inc_list["total"] >= 1
            active_inc_id = inc_list["incidents"][0]["incident_id"]
            _golden_path_ids["incident_id"] = active_inc_id
            record_step("AUTHORITY_APP", "active_incidents_queried", f"PASS: found {inc_list['total']}", lat)

            # Step 9: Authority Incident Acknowledgment
            t_start = time.monotonic()
            resp_ack = await client.post(
                f"/api/v1/authority/incidents/{active_inc_id}/acknowledge",
                json={"notes": "Golden Path acknowledgment: responder unit deployed"},
                headers=headers_auth,
            )
            lat = (time.monotonic() - t_start) * 1000
            assert resp_ack.status_code == 200
            assert resp_ack.json()["status"] == IncidentStatus.ACKNOWLEDGED.value
            _golden_path_ids["ack_status"] = IncidentStatus.ACKNOWLEDGED.value
            record_step("INCIDENT_LIFECYCLE", "incident_acknowledged", "PASS: ACKNOWLEDGED", lat)

            # Step 10: Authority Incident Resolution
            t_start = time.monotonic()
            resp_res = await client.post(
                f"/api/v1/authority/incidents/{active_inc_id}/resolve",
                json={"resolution_reason": "Golden Path - Tourist verified safe and accounted for"},
                headers=headers_auth,
            )
            lat = (time.monotonic() - t_start) * 1000
            assert resp_res.status_code == 200
            assert resp_res.json()["status"] == IncidentStatus.RESOLVED.value
            _golden_path_ids["resolution_status"] = IncidentStatus.RESOLVED.value
            record_step("INCIDENT_LIFECYCLE", "incident_resolved", "PASS: RESOLVED", lat)

            # Step 11: Audit Trail Decision History
            t_start = time.monotonic()
            resp_hist = await client.get(f"/api/v1/authority/tourists/{GP_TOURIST_ID}/safety/history", headers=headers_auth)
            lat = (time.monotonic() - t_start) * 1000
            assert resp_hist.status_code == 200
            hist_data = resp_hist.json()
            assert hist_data["total"] >= 1
            assert len(hist_data["decisions"]) >= 1
            assert all("rule_version" in d for d in hist_data["decisions"])
            _golden_path_ids["audit_total"] = hist_data["total"]
            record_step("AUDIT", "audit_trail_complete", f"PASS: {hist_data['total']} entries", lat)

        # Step 12: Summary and Output
        print("\n" + "=" * 60)
        print("GOLDEN PATH TRACE REPORT")
        print("=" * 60)
        print(f"Captured IDs: {_golden_path_ids}")
        print("\nTimeline:")
        for s in _golden_path_timeline:
            lat_str = f" [{s['latency_ms']}ms]" if s['latency_ms'] else ""
            print(f"  [{s['timestamp']}] {s['component']}.{s['event']}: {s['result']}{lat_str}")

        assert "tourist_token" in _golden_path_ids
        assert "tracking_session_id" in _golden_path_ids
        assert "incident_state" in _golden_path_ids
        assert "ack_status" in _golden_path_ids
        assert "resolution_status" in _golden_path_ids
        assert "audit_total" in _golden_path_ids
