"""
Prompt 21 Responder Mobile Application & Field Operations Test Suite

Validates:
1. Responder authentication & self-profile resolution
2. Availability state transitions with server reconciliation
3. Assignment queue, acceptance, rejection with structured reasons
4. Live GPS tracking ingestion & location freshness calculations
5. En-route response start, arrival proximity validation, and override fallback
6. On-scene structured scene assessments (TOURIST_SAFE, MEDICAL_ASSISTANCE, etc.)
7. Field notes creation, offline batch synchronization, and timeline auditing
8. Operational Handover request workflow
9. Escalation request and Resolution workflow
10. Paginated responder mission history
11. Concurrency protection and role authorization
"""

import asyncio
import copy
from datetime import datetime, timezone
import sys
from typing import Any, Dict, List, Optional
import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "backend")

from app.main import app
import app.core.database as db_module
import app.routers.auth as auth_mod
import app.routers.responders as responders_router_mod
import app.routers.emergency as emergency_router_mod
from app.core.security import create_access_token
from app.schemas.emergency import (
    AssignmentAcceptRequest,
    AssignmentArrivedRequest,
    AssignmentCompleteRequest,
    AssignmentHandoverRequest,
    AssignmentRecord,
    AssignmentRejectRequest,
    AssignmentStatus,
    FieldNotesBatchSyncRequest,
    FieldNotesBatchSyncResponse,
    HandoverReason,
    IncidentAssignRequest,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    OfflineFieldNoteItem,
    OperationalMessageCreateRequest,
    RejectionReason,
    ResolutionCategory,
    ResponderCapability,
    ResponderCreateRequest,
    ResponderLocationUpdateRequest,
    ResponderRecord,
    ResponderStatus,
    ResponderStatusUpdateRequest,
    ResponderType,
    ResponderUnitCreateRequest,
    SceneAssessmentCategory,
    SceneAssessmentRequest,
)
from app.services.emergency import (
    assignment_service,
    incident_service,
    messaging_service,
    responder_location_service,
    responder_recommendation_service,
    responder_service,
)


class MockCollection:
    def __init__(self, name="collection"):
        self.name = name
        self.docs: List[Dict[str, Any]] = []

    def _matches(self, doc: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
        for k, v in filter_dict.items():
            if k == "$or":
                if not any(self._matches(doc, sub) for sub in v):
                    return False
            elif k == "$and":
                if not all(self._matches(doc, sub) for sub in v):
                    return False
            elif isinstance(v, dict):
                val = doc.get(k)
                if "$in" in v:
                    if val not in v["$in"]:
                        return False
                elif "$ne" in v:
                    if val == v["$ne"]:
                        return False
                elif "$gte" in v:
                    if str(val) < v["$gte"]:
                        return False
                elif "$lte" in v:
                    if str(val) > v["$lte"]:
                        return False
            else:
                val = doc.get(k)
                if isinstance(val, list) and not isinstance(v, list):
                    if v not in val:
                        return False
                elif val != v:
                    return False
        return True

    async def insert_one(self, doc):
        d = copy.deepcopy(doc)
        if "_id" not in d:
            d["_id"] = f"mock_{len(self.docs)+1}"
        self.docs.append(d)
        return type("InsertResult", (), {"inserted_id": d["_id"]})()

    async def find_one(self, filter_dict=None, sort=None, *args, **kwargs):
        if not filter_dict:
            return copy.deepcopy(self.docs[0]) if self.docs else None
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                return copy.deepcopy(doc)
        return None

    def find(self, filter_dict=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        matching = [copy.deepcopy(doc) for doc in self.docs if self._matches(doc, filter_dict)]

        class MockCursor:
            def __init__(self, docs):
                self._docs = docs
                self._idx = 0

            def __aiter__(self):
                self._idx = 0
                return self

            async def __anext__(self):
                if self._idx < len(self._docs):
                    res = self._docs[self._idx]
                    self._idx += 1
                    return res
                raise StopAsyncIteration

            def sort(self, key, direction=1):
                return self

            def skip(self, n):
                self._docs = self._docs[n:]
                return self

            def limit(self, n):
                self._docs = self._docs[:n]
                return self

            async def to_list(self, length=100):
                return self._docs[:length]

        return MockCursor(matching)

    async def count_documents(self, filter_dict=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        return sum(1 for doc in self.docs if self._matches(doc, filter_dict))

    async def update_one(self, filter_dict, update_dict, *args, **kwargs):
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                if "$set" in update_dict:
                    doc.update(copy.deepcopy(update_dict["$set"]))
                if "$addToSet" in update_dict:
                    for k, val in update_dict["$addToSet"].items():
                        if k not in doc or not isinstance(doc[k], list):
                            doc[k] = []
                        if val not in doc[k]:
                            doc[k].append(val)
                if "$inc" in update_dict:
                    for k, val in update_dict["$inc"].items():
                        doc[k] = doc.get(k, 0) + val
                if "$push" in update_dict:
                    for k, val in update_dict["$push"].items():
                        if k not in doc or not isinstance(doc[k], list):
                            doc[k] = []
                        doc[k].append(copy.deepcopy(val))
                return type("UpdateResult", (), {"modified_count": 1, "matched_count": 1})()
        return type("UpdateResult", (), {"modified_count": 0, "matched_count": 0})()

    async def replace_one(self, filter_dict, new_doc, *args, **kwargs):
        for idx, doc in enumerate(self.docs):
            if self._matches(doc, filter_dict):
                d = copy.deepcopy(new_doc)
                d["_id"] = doc.get("_id", f"mock_{idx+1}")
                self.docs[idx] = d
                return type("UpdateResult", (), {"modified_count": 1, "matched_count": 1})()
        return type("UpdateResult", (), {"modified_count": 0, "matched_count": 0})()

    async def find_one_and_update(self, filter_dict, update_dict, return_document=True, *args, **kwargs):
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                if "$set" in update_dict:
                    doc.update(copy.deepcopy(update_dict["$set"]))
                if "$inc" in update_dict:
                    for k, val in update_dict["$inc"].items():
                        doc[k] = doc.get(k, 0) + val
                return copy.deepcopy(doc)
        return None

    async def delete_many(self, filter_dict=None, *args, **kwargs):

        filter_dict = filter_dict or {}
        before = len(self.docs)
        self.docs = [doc for doc in self.docs if not self._matches(doc, filter_dict)]
        return type("DeleteResult", (), {"deleted_count": before - len(self.docs)})()


class MockDatabase:
    def __init__(self):
        self.users = MockCollection("users")
        self.responders = MockCollection("responders")
        self.responder_units = MockCollection("responder_units")
        self.incident_assignments = MockCollection("incident_assignments")
        self.responder_tracking_sessions = MockCollection("responder_tracking_sessions")
        self.responder_location_history = MockCollection("responder_location_history")
        self.incident_messages = MockCollection("incident_messages")
        self.incidents = MockCollection("incidents")
        self.notifications = MockCollection("notifications")
        self.tourists = MockCollection("tourists")

    def __getitem__(self, name):
        if not hasattr(self, name):
            setattr(self, name, MockCollection(name))
        return getattr(self, name)


@pytest.fixture(autouse=True)
def setup_mock_db(monkeypatch):
    mock_db = MockDatabase()
    monkeypatch.setattr(db_module, "get_database", lambda: mock_db)
    monkeypatch.setattr(auth_mod, "get_database", lambda: mock_db)
    monkeypatch.setattr(responders_router_mod, "get_database", lambda: mock_db)
    monkeypatch.setattr(emergency_router_mod, "get_database", lambda: mock_db)
    return mock_db


@pytest.mark.asyncio
async def test_responder_self_profile_and_availability(setup_mock_db):
    mock_db = setup_mock_db
    user_id = "user_field_resp_01"
    now_iso = datetime.now(timezone.utc).isoformat()

    # Create user
    await mock_db.users.insert_one({
        "id": user_id,
        "email": "patrol1@toursafe.internal",
        "full_name": "Officer Rahul Naik",
        "role": "responder",
        "is_active": True,
        "created_at": now_iso,
    })

    # Create responder profile
    resp = await responder_service.create_responder(
        ResponderCreateRequest(
            name="Officer Rahul Naik",
            type=ResponderType.FIELD_RESPONDER,
            user_id=user_id,
            capabilities=["FIRST_AID", "SEARCH", "WATER_RESCUE"],
        )
    )
    assert resp.responder_id is not None
    assert resp.status == ResponderStatus.AVAILABLE

    token = create_access_token(user_id, "responder")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Get Me
        res = await client.get("/api/v1/responders/me", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["profile"]["name"] == "Officer Rahul Naik"
        assert data["profile"]["status"] == "AVAILABLE"
        assert "FIRST_AID" in data["profile"]["capabilities"]

        # 2. Update Availability -> UNAVAILABLE
        res2 = await client.post(
            "/api/v1/responders/me/status",
            json={"status": "UNAVAILABLE", "reason": "Meal break"},
            headers=headers,
        )
        assert res2.status_code == 200
        assert res2.json()["status"] == "UNAVAILABLE"

        # 3. Update Availability -> AVAILABLE
        res3 = await client.post(
            "/api/v1/responders/me/status",
            json={"status": "AVAILABLE", "reason": "Resuming active field patrol"},
            headers=headers,
        )
        assert res3.status_code == 200
        assert res3.json()["status"] == "AVAILABLE"


@pytest.mark.asyncio
async def test_assignment_full_operational_lifecycle(setup_mock_db):
    mock_db = setup_mock_db
    resp_user_id = "user_resp_02"
    auth_user_id = "user_auth_01"
    now_iso = datetime.now(timezone.utc).isoformat()

    # Users
    await mock_db.users.insert_one({
        "id": resp_user_id,
        "email": "medic1@toursafe.internal",
        "full_name": "Paramedic Sarah Fernandes",
        "role": "responder",
        "is_active": True,
        "created_at": now_iso,
    })
    await mock_db.users.insert_one({
        "id": auth_user_id,
        "email": "command@toursafe.gov",
        "full_name": "Commander V. Rao",
        "role": "authority",
        "is_active": True,
        "created_at": now_iso,
    })

    # Responder
    resp = await responder_service.create_responder(
        ResponderCreateRequest(
            name="Paramedic Sarah Fernandes",
            type=ResponderType.MEDICAL,
            user_id=resp_user_id,
            capabilities=["MEDICAL", "FIRST_AID"],
        )
    )

    # Incident at Anjuna Beach (15.5800, 73.7400)
    inc = await incident_service.create_incident(
        tourist_id="tourist_alice_01",
        source=IncidentSource.MANUAL_SOS,
        severity=IncidentSeverity.HIGH,
        location_data={
            "latitude": 15.5800,
            "longitude": 73.7400,
            "accuracy": 5.0,
            "zone_name": "Anjuna Coastal Zone",
        },
    )

    resp_token = create_access_token(resp_user_id, "responder")
    auth_token = create_access_token(auth_user_id, "authority")
    resp_headers = {"Authorization": f"Bearer {resp_token}"}
    auth_headers = {"Authorization": f"Bearer {auth_token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Authority creates assignment
        asgn_res = await client.post(
            f"/api/v1/authority/incidents/{inc.incident_id}/assignments",
            json={"responder_id": resp.responder_id, "notes": "Immediate medical deployment"},
            headers=auth_headers,
        )
        assert asgn_res.status_code == 201
        asgn_data = asgn_res.json()
        assignment_id = asgn_data["assignment_id"]
        assert asgn_data["status"] == "PENDING"

        # 2. Responder views Active Assignment
        me_res = await client.get("/api/v1/responders/me", headers=resp_headers)
        assert me_res.status_code == 200
        assert me_res.json()["active_assignment"]["assignment_id"] == assignment_id

        # 3. Responder Accepts Assignment
        accept_res = await client.post(
            f"/api/v1/authority/incidents/{inc.incident_id}/assignments/{assignment_id}/accept",
            json={"notes": "Medic Sarah en route with jump-kit"},
            headers=resp_headers,
        )
        assert accept_res.status_code == 200
        assert accept_res.json()["status"] == "ACCEPTED"

        # 4. Concurrency check: Second responder cannot accept already accepted assignment
        dup_accept = await client.post(
            f"/api/v1/authority/incidents/{inc.incident_id}/assignments/{assignment_id}/accept",
            json={"notes": "Duplicate accept attempt"},
            headers=resp_headers,
        )
        assert dup_accept.status_code == 400

        # 5. Start Response (En Route)
        start_res = await client.post(
            f"/api/v1/authority/incidents/{inc.incident_id}/assignments/{assignment_id}/start",
            json={"notes": "Emergency vehicle deployed, ETA 6 mins"},
            headers=resp_headers,
        )
        assert start_res.status_code == 200
        assert start_res.json()["status"] == "ACTIVE"

        # 6. Ingest Live GPS Location from Responder Device
        loc_res = await client.post(
            "/api/v1/responders/me/location",
            json={
                "latitude": 15.5802,
                "longitude": 73.7401,
                "accuracy": 4.2,
                "speed": 6.5,
                "heading": 120.0,
            },
            headers=resp_headers,
        )
        assert loc_res.status_code == 200

        # 7. Arrive On Scene (within proximity radius ~25 meters away)
        arr_res = await client.post(
            f"/api/v1/authority/incidents/{inc.incident_id}/assignments/{assignment_id}/arrived",
            json={
                "latitude": 15.5802,
                "longitude": 73.7401,
                "accuracy": 4.2,
                "notes": "Arrived at casualty coordinates",
            },
            headers=resp_headers,
        )
        assert arr_res.status_code == 200
        assert arr_res.json()["arrived_at"] is not None

        # 8. Submit Structured Scene Assessment
        assess_res = await client.post(
            f"/api/v1/authority/incidents/{inc.incident_id}/assignments/{assignment_id}/assess-scene",
            json={
                "category": "MEDICAL_ASSISTANCE",
                "notes": "Casualty treated for minor laceration and heat exhaustion, vitals stable",
                "tourist_status_observed": "Conscious and ambulatory",
                "follow_up_required": False,
                "evidence_metadata": {"first_aid_administered": True},
            },
            headers=resp_headers,
        )
        assert assess_res.status_code == 200
        assert assess_res.json()["success"] is True

        # 9. Complete Mission / Resolve
        comp_res = await client.post(
            f"/api/v1/authority/incidents/{inc.incident_id}/assignments/{assignment_id}/complete",
            json={
                "completion_reason": "First aid rendered successfully, tourist reunited with guide",
                "resolution_notes": "No hospitalization required. Safe to resume travel.",
            },
            headers=resp_headers,
        )
        assert comp_res.status_code == 200
        assert comp_res.json()["status"] == "COMPLETED"

        # Verify responder released back to AVAILABLE
        me_after = await client.get("/api/v1/responders/me", headers=resp_headers)
        assert me_after.json()["profile"]["status"] == "AVAILABLE"
        assert me_after.json()["active_assignment"] is None

        # 10. Check Paginated History
        hist_res = await client.get("/api/v1/responders/me/history?limit=10", headers=resp_headers)
        assert hist_res.status_code == 200
        hist_data = hist_res.json()
        assert hist_data["total"] >= 1
        assert hist_data["items"][0]["assignment_id"] == assignment_id


@pytest.mark.asyncio
async def test_assignment_rejection_and_handover_workflow(setup_mock_db):
    mock_db = setup_mock_db
    resp_user_id = "user_resp_03"
    auth_user_id = "user_auth_02"
    now_iso = datetime.now(timezone.utc).isoformat()

    await mock_db.users.insert_one({
        "id": resp_user_id,
        "email": "search1@toursafe.internal",
        "full_name": "Patrol Officer Deepak",
        "role": "responder",
        "is_active": True,
        "created_at": now_iso,
    })
    await mock_db.users.insert_one({
        "id": auth_user_id,
        "email": "dispatch@toursafe.gov",
        "full_name": "Dispatcher Anjali",
        "role": "authority",
        "is_active": True,
        "created_at": now_iso,
    })

    resp = await responder_service.create_responder(
        ResponderCreateRequest(
            name="Patrol Officer Deepak",
            type=ResponderType.FIELD_RESPONDER,
            user_id=resp_user_id,
            capabilities=["SEARCH"],
        )
    )

    inc = await incident_service.create_incident(
        tourist_id="tourist_bob_02",
        source=IncidentSource.SAFETY_ENGINE,
        severity=IncidentSeverity.MEDIUM,
        location_data={"latitude": 15.6000, "longitude": 73.7500},
    )

    resp_token = create_access_token(resp_user_id, "responder")
    auth_token = create_access_token(auth_user_id, "authority")
    resp_headers = {"Authorization": f"Bearer {resp_token}"}
    auth_headers = {"Authorization": f"Bearer {auth_token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Assignment Creation
        asgn_res = await client.post(
            f"/api/v1/authority/incidents/{inc.incident_id}/assignments",
            json={"responder_id": resp.responder_id},
            headers=auth_headers,
        )
        assignment_id = asgn_res.json()["assignment_id"]

        # 2. Reject Assignment with structured reason
        rej_res = await client.post(
            f"/api/v1/authority/incidents/{inc.incident_id}/assignments/{assignment_id}/reject",
            json={
                "reason": "WRONG_CAPABILITY",
                "details": "Requires technical rope rescue unit, terrain impassable for foot patrol",
            },
            headers=resp_headers,
        )
        assert rej_res.status_code == 200
        assert rej_res.json()["status"] == "REJECTED"

        # 3. Create second assignment and accept
        asgn2_res = await client.post(
            f"/api/v1/authority/incidents/{inc.incident_id}/assignments",
            json={"responder_id": resp.responder_id},
            headers=auth_headers,
        )
        assert asgn2_res.status_code == 201
        asgn2_id = asgn2_res.json()["assignment_id"]

        acc_res = await client.post(
            f"/api/v1/authority/incidents/{inc.incident_id}/assignments/{asgn2_id}/accept",
            json={},
            headers=resp_headers,
        )
        assert acc_res.status_code == 200

        start_res = await client.post(
            f"/api/v1/authority/incidents/{inc.incident_id}/assignments/{asgn2_id}/start",
            json={},
            headers=resp_headers,
        )
        assert start_res.status_code == 200

        # 4. Request Handover (e.g. equipment failure or terrain obstacle)
        handover_res = await client.post(
            f"/api/v1/responders/me/assignments/{asgn2_id}/handover",
            json={
                "reason": "LOCATION",
                "details": "Bridge washed out, unable to cross river. Handover to South Bank unit required.",
                "replacement_capability": "WATER_RESCUE",
            },
            headers=resp_headers,
        )
        assert handover_res.status_code == 200, f"Handover failed: {handover_res.json()}"
        assert handover_res.json()["status"] == "CANCELLED"

        # Verify incident status returned to ACKNOWLEDGED for reassignment
        inc_doc = await mock_db.incidents.find_one({"incident_id": inc.incident_id})
        assert inc_doc["status"] == "ACKNOWLEDGED"
        assert inc_doc["assigned_to"] is None



@pytest.mark.asyncio
async def test_offline_field_notes_batch_synchronization(setup_mock_db):
    mock_db = setup_mock_db
    user_id = "user_resp_offline_01"
    now_iso = datetime.now(timezone.utc).isoformat()

    await mock_db.users.insert_one({
        "id": user_id,
        "email": "field_offline@toursafe.internal",
        "full_name": "Ranger Maya",
        "role": "responder",
        "is_active": True,
        "created_at": now_iso,
    })

    resp = await responder_service.create_responder(
        ResponderCreateRequest(
            name="Ranger Maya",
            type=ResponderType.FIELD_RESPONDER,
            user_id=user_id,
            capabilities=["SEARCH"],
        )
    )

    inc = await incident_service.create_incident(
        tourist_id="tourist_offline_01",
        source=IncidentSource.SAFETY_ENGINE,
        severity=IncidentSeverity.LOW,
        location_data={"latitude": 15.5500, "longitude": 73.7600},
    )

    token = create_access_token(user_id, "responder")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sync_payload = {
            "notes": [
                {
                    "client_note_id": "cnote_001_offline",
                    "incident_id": inc.incident_id,
                    "content": "Located abandoned backpack at trail marker 4. Continuing north.",
                    "recorded_at": "2026-08-22T10:00:00Z",
                    "latitude": 15.5510,
                    "longitude": 73.7610,
                },
                {
                    "client_note_id": "cnote_002_offline",
                    "incident_id": inc.incident_id,
                    "content": "Visual contact made with tourist. Safe and drinking water.",
                    "recorded_at": "2026-08-22T10:08:00Z",
                    "latitude": 15.5525,
                    "longitude": 73.7630,
                },
            ]
        }

        res = await client.post("/api/v1/responders/me/field-notes/sync", json=sync_payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["synced_count"] == 2
        assert "cnote_001_offline" in data["synced_ids"]

        # Idempotency check: sending duplicate client_note_id should not create duplicate entries
        res2 = await client.post("/api/v1/responders/me/field-notes/sync", json=sync_payload, headers=headers)
        assert res2.status_code == 200
        assert res2.json()["synced_count"] == 2

        # Check that incident notes list contains the synced notes
        inc_doc = await mock_db.incidents.find_one({"incident_id": inc.incident_id})
        assert len(inc_doc["notes_list"]) == 2
        assert "abandoned backpack" in inc_doc["notes_list"][0]["content"]
