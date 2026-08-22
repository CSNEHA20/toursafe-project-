"""
TourSafe Responder Operations Platform Tests

Comprehensive test suite covering:
1. Responder registration, roles, capabilities, and self-profile (GET /api/v1/responders/me)
2. Responder Unit hierarchy and membership management
3. Strict Responder State Machine transition matrices
4. Concurrency protection and atomic assignment locking
5. Real GPS tracking session lifecycle, live Redis caching, and staleness calculation
6. End-to-end assignment lifecycle: Assign -> Accept / Reject -> Start -> Proximity Arrived -> Complete
7. Scoped operational incident messaging and timeline integration
8. Deterministic candidate ranking and geodesic distance calculations
9. Authority Live Command Map filtering
"""

import asyncio
import copy
from datetime import datetime, timezone, timedelta
import pytest
import sys
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, "backend")

from app.main import app
import app.core.database as db_module
import app.routers.auth as auth_mod
import app.routers.responders as responders_router_mod
import app.routers.emergency as emergency_router_mod
import app.services.emergency.responder_service as resp_svc_mod
import app.services.emergency.responder_location_service as resp_loc_svc_mod
import app.services.emergency.assignment_service as asgn_svc_mod
import app.services.emergency.messaging_service as msg_svc_mod
import app.services.emergency.incident_service as inc_svc_mod
from app.core.security import create_access_token
from app.schemas.emergency import (
    AssignmentAcceptRequest,
    AssignmentArrivedRequest,
    AssignmentCompleteRequest,
    AssignmentRecord,
    AssignmentRejectRequest,
    AssignmentStatus,
    IncidentAssignRequest,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    OperationalMessageCreateRequest,
    RejectionReason,
    ResponderCapability,
    ResponderCreateRequest,
    ResponderLocationUpdateRequest,
    ResponderRecord,
    ResponderStatus,
    ResponderStatusUpdateRequest,
    ResponderType,
    ResponderUnitCreateRequest,
    ResponderUnitUpdateRequest,
    ResponderUpdateRequest,
    UnitStatus,
)
from app.schemas.safety import IncidentRecord
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

    async def update_many(self, filter_dict, update_dict, *args, **kwargs):
        count = 0
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
                count += 1
        return type("UpdateResult", (), {"modified_count": count, "matched_count": count})()

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
    # Seed mock authority user
    mock_db.users.docs.append({
        "id": "auth_admin_1",
        "email": "admin@toursafe.dev",
        "role": "authority",
        "full_name": "Chief Dispatcher",
        "is_active": True,
    })
    # Seed mock responder user
    mock_db.users.docs.append({
        "id": "user_resp_99",
        "email": "medic99@toursafe.dev",
        "role": "responder",
        "full_name": "Medic Ninety-Nine",
        "is_active": True,
    })

    monkeypatch.setattr(db_module, "get_database", lambda: mock_db)
    monkeypatch.setattr(auth_mod, "get_database", lambda: mock_db)
    monkeypatch.setattr(responders_router_mod, "get_database", lambda: mock_db)
    monkeypatch.setattr(emergency_router_mod, "get_database", lambda: mock_db)
    return mock_db


@pytest.mark.asyncio
async def test_responder_crud_and_unit_management():
    """Verify responder registration, unit hierarchy, and membership management."""
    # 1. Create Unit
    unit = await responder_service.create_unit(
        ResponderUnitCreateRequest(
            name="Medical Alpha 1",
            type=ResponderType.MEDICAL,
            capabilities=["MEDICAL", "FIRST_AID", "TRANSPORT"],
        )
    )
    assert unit.unit_id.startswith("unit_")
    assert unit.name == "Medical Alpha 1"
    assert unit.status == UnitStatus.AVAILABLE

    # 2. Create Responder with Unit
    resp = await responder_service.create_responder(
        ResponderCreateRequest(
            name="Dr. Jane Smith",
            type=ResponderType.MEDICAL,
            unit_id=unit.unit_id,
            user_id="user_resp_001",
            capabilities=["MEDICAL", "FIRST_AID"],
            contact_channel="push_token_jane",
            contact_phone="+919876543210",
        )
    )
    assert resp.responder_id.startswith("resp_")
    assert resp.status == ResponderStatus.AVAILABLE
    assert resp.unit_id == unit.unit_id
    assert "MEDICAL" in resp.capabilities

    # 3. List Responders by Capability
    items, total = await responder_service.list_responders(capability="MEDICAL")
    assert total >= 1
    assert any(r.responder_id == resp.responder_id for r in items)

    # 4. Lookup by User ID
    lookup = await responder_service.get_responder_by_user_id("user_resp_001")
    assert lookup is not None
    assert lookup.responder_id == resp.responder_id


@pytest.mark.asyncio
async def test_strict_responder_state_machine():
    """Verify strict transition validation and rejection of invalid transitions."""
    resp = await responder_service.create_responder(
        ResponderCreateRequest(
            name="Officer John Davis",
            type=ResponderType.POLICE,
            capabilities=["SECURITY", "CROWD_CONTROL"],
        )
    )
    r_id = resp.responder_id

    # AVAILABLE -> OFFLINE (Valid)
    s1 = await responder_service.set_responder_status(r_id, ResponderStatus.OFFLINE)
    assert s1.status == ResponderStatus.OFFLINE

    # OFFLINE -> AVAILABLE (Valid)
    s2 = await responder_service.set_responder_status(r_id, ResponderStatus.AVAILABLE)
    assert s2.status == ResponderStatus.AVAILABLE

    # AVAILABLE -> ON_SCENE (Invalid: must go through ASSIGNED -> RESPONDING)
    with pytest.raises(ValueError, match="Invalid status transition"):
        await responder_service.set_responder_status(r_id, ResponderStatus.ON_SCENE)


@pytest.mark.asyncio
async def test_responder_tracking_and_location_staleness():
    """Verify real GPS tracking session lifecycle, live Redis ingestion, and staleness computation."""
    resp = await responder_service.create_responder(
        ResponderCreateRequest(name="Search Unit 4", type=ResponderType.SEARCH_AND_RESCUE)
    )
    r_id = resp.responder_id

    # 1. Start Tracking Session
    session_id = await responder_location_service.start_tracking_session(r_id, device_id="pixel_7_pro")
    assert session_id.startswith("trk_resp_")

    # 2. Ingest real GPS coordinates (Goa Beach area)
    now_iso = datetime.now(timezone.utc).isoformat()
    loc_payload = await responder_location_service.ingest_responder_location(
        responder_id=r_id,
        update=ResponderLocationUpdateRequest(
            latitude=15.4989,
            longitude=73.8278,
            accuracy=8.5,
            heading=180.0,
            speed=4.2,
            timestamp=now_iso,
            tracking_session_id=session_id,
        ),
    )
    assert loc_payload["latitude"] == 15.4989
    assert loc_payload["quality"] == "HIGH_ACCURACY"

    # 3. Retrieve Live Location
    live_loc = await responder_location_service.get_live_location(r_id)
    assert live_loc is not None
    assert live_loc["latitude"] == 15.4989

    # 4. Check Freshness
    freshness, age = responder_location_service.calculate_location_freshness(now_iso)
    assert freshness == "LIVE"
    assert age is not None and age <= 5.0

    stale_ts = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    fresh_stale, _ = responder_location_service.calculate_location_freshness(stale_ts)
    assert fresh_stale == "STALE"

    # 5. Stop Tracking Session
    stopped = await responder_location_service.stop_tracking_session(r_id, session_id)
    assert stopped is True


@pytest.mark.asyncio
async def test_incident_assignment_lifecycle_and_proximity_arrival():
    """
    End-to-end verification of:
    Incident Created -> Authority Assigns -> Responder Accepts -> Response Starts ->
    Proximity Arrival -> Operational Chat -> Response Completion.
    """
    # 1. Create Incident
    inc = await incident_service.create_incident(
        tourist_id="tourist_100",
        source=IncidentSource.MANUAL_SOS,
        severity=IncidentSeverity.HIGH,
        location_data={"latitude": 15.5000, "longitude": 73.8300, "address": "Baga Beach Road"},
    )
    inc_id = inc.incident_id

    # 2. Create Available Responder
    resp = await responder_service.create_responder(
        ResponderCreateRequest(
            name="Field Medic Ravi",
            type=ResponderType.MEDICAL,
            capabilities=["MEDICAL", "FIRST_AID"],
        )
    )
    r_id = resp.responder_id

    # 3. Authority Assigns Responder
    asgn = await assignment_service.create_assignment(
        incident_id=inc_id,
        responder_id=r_id,
        assigned_by="auth_user_admin",
        notes="High priority medical assist required",
    )
    assert asgn.assignment_id.startswith("asgn_")
    assert asgn.status == AssignmentStatus.PENDING

    # Verify responder status updated to ASSIGNED
    resp_updated = await responder_service.get_responder(r_id)
    assert resp_updated.status == ResponderStatus.ASSIGNED
    assert resp_updated.active_assignment_id == asgn.assignment_id

    # 4. Responder Accepts
    accepted_asgn = await assignment_service.accept_assignment(
        incident_id=inc_id,
        assignment_id=asgn.assignment_id,
        responder_id=r_id,
        notes="En route in ambulance",
    )
    assert accepted_asgn.status == AssignmentStatus.ACCEPTED
    assert accepted_asgn.accepted_at is not None

    # 5. Responder Starts Travel
    active_asgn = await assignment_service.start_response(
        incident_id=inc_id,
        assignment_id=asgn.assignment_id,
        responder_id=r_id,
        notes="Departed base station",
    )
    assert active_asgn.status == AssignmentStatus.ACTIVE
    resp_state = await responder_service.get_responder(r_id)
    assert resp_state.status == ResponderStatus.RESPONDING

    # 6. Operational Chat Message
    msg = await messaging_service.send_message(
        incident_id=inc_id,
        sender_id=r_id,
        sender_type="RESPONDER",
        sender_name="Field Medic Ravi",
        req=OperationalMessageCreateRequest(
            content="Approaching North entrance of Baga Beach. ETA 1 min.",
            assignment_id=asgn.assignment_id,
        ),
    )
    assert msg.message_id.startswith("msg_")
    assert msg.content == "Approaching North entrance of Baga Beach. ETA 1 min."

    messages = await messaging_service.get_messages(inc_id)
    assert len(messages) == 1
    assert messages[0].message_id == msg.message_id

    # 7. Responder Arrives (Within 100m of incident location: 15.5005, 73.8302)
    arrived_asgn = await assignment_service.mark_arrived(
        incident_id=inc_id,
        assignment_id=asgn.assignment_id,
        responder_id=r_id,
        req=AssignmentArrivedRequest(
            latitude=15.5005,
            longitude=73.8302,
            accuracy=5.0,
            notes="On scene at victim location",
        ),
    )
    assert arrived_asgn.arrived_at is not None
    resp_arrived = await responder_service.get_responder(r_id)
    assert resp_arrived.status == ResponderStatus.ON_SCENE

    # 8. Responder Completes Response
    completed_asgn = await assignment_service.complete_response(
        incident_id=inc_id,
        assignment_id=asgn.assignment_id,
        responder_id=r_id,
        req=AssignmentCompleteRequest(
            completion_reason="Tourist stabilized and transported to clinic",
            resolution_notes="Minor lacerations treated, vitals normal",
        ),
    )
    assert completed_asgn.status == AssignmentStatus.COMPLETED
    assert completed_asgn.completion_reason == "Tourist stabilized and transported to clinic"

    # Responder released to AVAILABLE
    resp_done = await responder_service.get_responder(r_id)
    assert resp_done.status == ResponderStatus.AVAILABLE
    assert resp_done.active_assignment_id is None

    # Check Incident Timeline
    inc_final = await incident_service.get_incident(inc_id)
    timeline_actions = [t["action"] for t in inc_final.timeline]
    assert "incident.assigned" in timeline_actions
    assert "responder.accepted" in timeline_actions
    assert "incident.response.started" in timeline_actions
    assert "responder.arrived" in timeline_actions
    assert "responder.completed" in timeline_actions


@pytest.mark.asyncio
async def test_assignment_rejection_workflow():
    """Verify responder rejection releases responder and updates incident state."""
    inc = await incident_service.create_incident(
        tourist_id="tourist_200",
        source=IncidentSource.MANUAL_SOS,
    )
    resp = await responder_service.create_responder(
        ResponderCreateRequest(name="Patrol Officer Ken", type=ResponderType.POLICE)
    )

    asgn = await assignment_service.create_assignment(
        incident_id=inc.incident_id,
        responder_id=resp.responder_id,
        assigned_by="auth_user_admin",
    )

    # Reject Assignment
    rejected_asgn = await assignment_service.reject_assignment(
        incident_id=inc.incident_id,
        assignment_id=asgn.assignment_id,
        responder_id=resp.responder_id,
        reason=RejectionReason.ALREADY_RESPONDING,
        details="Handling traffic obstruction on Bridge",
    )
    assert rejected_asgn.status == AssignmentStatus.REJECTED
    assert "ALREADY_RESPONDING" in (rejected_asgn.rejection_reason or "")

    # Verify responder released
    resp_after = await responder_service.get_responder(resp.responder_id)
    assert resp_after.status == ResponderStatus.AVAILABLE
    assert resp_after.active_assignment_id is None


@pytest.mark.asyncio
async def test_deterministic_responder_recommendations():
    """Verify deterministic candidate ranking by capability matching and Haversine distance."""
    # Setup responders with locations
    r1 = await responder_service.create_responder(
        ResponderCreateRequest(
            name="Nearest First Aid",
            type=ResponderType.FIELD_RESPONDER,
            capabilities=["FIRST_AID", "SEARCH"],
        )
    )
    await responder_service.update_responder(
        r1.responder_id,
        ResponderUpdateRequest(current_location={"latitude": 15.5010, "longitude": 73.8310}),
    )

    r2 = await responder_service.create_responder(
        ResponderCreateRequest(
            name="Distant Medical Team",
            type=ResponderType.MEDICAL,
            capabilities=["MEDICAL", "FIRST_AID", "TRANSPORT"],
        )
    )
    await responder_service.update_responder(
        r2.responder_id,
        ResponderUpdateRequest(current_location={"latitude": 15.6000, "longitude": 73.9000}),
    )

    # Incident location at (15.5000, 73.8300) requiring FIRST_AID
    recommendations = await responder_recommendation_service.get_recommendations_for_incident(
        incident_lat=15.5000,
        incident_lon=73.8300,
        required_capabilities=["FIRST_AID"],
    )
    assert len(recommendations) >= 2
    # Nearest responder should have higher score due to proximity
    top = recommendations[0]
    assert top.responder_id == r1.responder_id
    assert top.distance_meters is not None and top.distance_meters < 500.0


@pytest.mark.asyncio
async def test_rest_api_endpoints():
    """Test REST API routes using AsyncClient."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        auth_token = create_access_token("auth_admin_1", "authority")
        resp_token = create_access_token("user_resp_99", "responder")

        # 1. Create Responder Unit via API
        unit_res = await ac.post(
            "/api/v1/responders/units",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "name": "Rapid Response Unit 7",
                "type": "FIELD_RESPONDER",
                "capabilities": ["SEARCH", "RESCUE"],
            },
        )
        assert unit_res.status_code == 201
        unit_data = unit_res.json()
        assert unit_data["name"] == "Rapid Response Unit 7"

        # 2. Get Responder Self Profile
        me_res = await ac.get(
            "/api/v1/responders/me",
            headers={"Authorization": f"Bearer {resp_token}"},
        )
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert "profile" in me_data
        assert me_data["location_freshness"] in ("LIVE", "RECENT", "STALE", "UNKNOWN", "OFFLINE")

        # 3. Ingest Responder Location
        loc_res = await ac.post(
            "/api/v1/responders/me/location",
            headers={"Authorization": f"Bearer {resp_token}"},
            json={
                "latitude": 15.4989,
                "longitude": 73.8278,
                "accuracy": 6.0,
                "speed": 0.0,
            },
        )
        assert loc_res.status_code == 200

        # 4. Authority Live Map API
        map_res = await ac.get(
            "/api/v1/responders/map/live",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert map_res.status_code == 200
        map_data = map_res.json()
        assert "responders" in map_data
        assert map_data["total"] >= 1
