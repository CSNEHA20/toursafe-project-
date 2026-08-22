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
import app.routers.emergency as emergency_router_mod
import app.services.emergency.incident_service as inc_svc_mod
import app.services.emergency.sos_service as sos_svc_mod
import app.services.emergency.responder_service as resp_svc_mod
import app.services.emergency.escalation_engine as esc_eng_mod
import app.services.emergency.notifications as notif_svc_mod
import app.services.safety.repository as safety_repo_mod
import app.services.location_service as location_service_mod
from app.core.security import create_access_token
from app.schemas.emergency import (
    IncidentAssessRequest,
    IncidentAssignRequest,
    IncidentCancelRequest,
    IncidentCloseRequest,
    IncidentEscalateRequest,
    IncidentNoteCreateRequest,
    IncidentResponseStartRequest,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    NotificationChannel,
    NotificationStatus,
    ResolutionCategory,
    ResponderCreateRequest,
    ResponderStatus,
    ResponderType,
    ResponderUpdateRequest,
    SOSCancelRequest,
    SOSRequest,
)
from app.schemas.location import (
    LiveLocationPayload,
    LiveLocationResponse,
    LocationStaleness,
)
from app.schemas.safety import IncidentRecord
from app.services.emergency import (
    escalation_engine,
    incident_service,
    notification_service,
    responder_service,
    sos_service,
)
from app.services.location_service import location_service


# Mock MongoDB In-Memory Storage
class MockCollection:
    def __init__(self, name="collection"):
        self.name = name
        self.docs: List[Dict[str, Any]] = []

    def _matches(self, doc: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
        for k, v in filter_dict.items():
            if k == "$or":
                if not any(self._matches(doc, sub) for sub in v):
                    return False
            elif isinstance(v, dict):
                val = doc.get(k)
                if "$in" in v:
                    if val not in v["$in"]:
                        return False
                elif "$gte" in v:
                    if str(val) < v["$gte"]:
                        return False
                elif "$lte" in v:
                    if str(val) > v["$lte"]:
                        return False
                elif "$regex" in v:
                    import re
                    pattern = re.compile(v["$regex"], re.IGNORECASE if v.get("$options") == "i" else 0)
                    if not pattern.search(str(val or "")):
                        return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    async def insert_one(self, doc):
        d = copy.deepcopy(doc)
        if "_id" not in d:
            d["_id"] = f"mock_{len(self.docs)+1}"
        self.docs.append(d)
        return type("InsertResult", (), {"inserted_id": d["_id"]})()

    async def find_one(self, filter_dict=None, sort=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        matches = [d for d in self.docs if self._matches(d, filter_dict)]
        if not matches:
            return None
        if sort:
            sort_field, sort_order = sort[0]
            matches.sort(key=lambda x: x.get(sort_field, ""), reverse=(sort_order == -1))
        return copy.deepcopy(matches[0])

    def find(self, filter_dict=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        matches = [copy.deepcopy(d) for d in self.docs if self._matches(d, filter_dict)]

        class AsyncCursor:
            def __init__(self, items):
                self.items = items
                self.index = 0

            def sort(self, key, order=1):
                self.items.sort(key=lambda x: x.get(key, ""), reverse=(order == -1))
                return self

            def skip(self, n):
                self.items = self.items[n:]
                return self

            def limit(self, n):
                self.items = self.items[:n]
                return self

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index < len(self.items):
                    item = self.items[self.index]
                    self.index += 1
                    return item
                raise StopAsyncIteration

            async def to_list(self, length=100):
                return self.items[:length]

        return AsyncCursor(matches)

    async def count_documents(self, filter_dict=None):
        filter_dict = filter_dict or {}
        return sum(1 for d in self.docs if self._matches(d, filter_dict))

    async def update_one(self, filter_dict, update_dict, upsert=False):
        filter_dict = filter_dict or {}
        for d in self.docs:
            if self._matches(d, filter_dict):
                if "$set" in update_dict:
                    d.update(copy.deepcopy(update_dict["$set"]))
                if "$inc" in update_dict:
                    for ik, iv in update_dict["$inc"].items():
                        d[ik] = d.get(ik, 0) + iv
                if "$push" in update_dict:
                    for pk, pv in update_dict["$push"].items():
                        if pk not in d:
                            d[pk] = []
                        d[pk].append(copy.deepcopy(pv))
                return type("UpdateResult", (), {"matched_count": 1, "modified_count": 1})()
        if upsert:
            new_doc = copy.deepcopy(filter_dict)
            if "$set" in update_dict:
                new_doc.update(copy.deepcopy(update_dict["$set"]))
            self.docs.append(new_doc)
            return type("UpdateResult", (), {"matched_count": 0, "upserted_id": "new_1"})()
        return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0})()

    async def replace_one(self, filter_dict, new_doc, upsert=False):
        for i, d in enumerate(self.docs):
            if self._matches(d, filter_dict):
                doc_copy = copy.deepcopy(new_doc)
                if "_id" in d and "_id" not in doc_copy:
                    doc_copy["_id"] = d["_id"]
                self.docs[i] = doc_copy
                return type("UpdateResult", (), {"matched_count": 1, "modified_count": 1})()
        if upsert:
            self.docs.append(copy.deepcopy(new_doc))
            return type("UpdateResult", (), {"matched_count": 0, "upserted_id": "new_1"})()
        return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0})()

    async def find_one_and_update(self, filter_dict, update_dict, return_document=True):
        for d in self.docs:
            if self._matches(d, filter_dict):
                if "$set" in update_dict:
                    d.update(copy.deepcopy(update_dict["$set"]))
                return copy.deepcopy(d)
        return None


class MockDatabase:
    def __init__(self):
        self.incidents = MockCollection("incidents")
        self.sos_events = MockCollection("sos_events")
        self.responders = MockCollection("responders")
        self.responder_units = MockCollection("responder_units")
        self.incident_assignments = MockCollection("incident_assignments")
        self.incident_messages = MockCollection("incident_messages")
        self.responder_tracking_sessions = MockCollection("responder_tracking_sessions")
        self.responder_location_history = MockCollection("responder_location_history")
        self.notifications = MockCollection("notifications")
        self.tourists = MockCollection("tourists")
        self.users = MockCollection("users")
        self.emergency_contacts = MockCollection("emergency_contacts")
        self.location_history = MockCollection("location_history")

    def __getitem__(self, name):
        if not hasattr(self, name):
            setattr(self, name, MockCollection(name))
        return getattr(self, name)

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        new_col = MockCollection(name)
        setattr(self, name, new_col)
        return new_col


@pytest.fixture(autouse=True)
def mock_db_fixture(monkeypatch):
    mock_db = MockDatabase()
    # Seed users
    mock_db.users.docs.append({
        "id": "tourist_1",
        "email": "tourist@toursafe.dev",
        "role": "tourist",
        "is_active": True,
    })
    mock_db.tourists.docs.append({
        "id": "tourist_1",
        "user_id": "tourist_1",
        "full_name": "Test Traveler",
        "emergency_contacts": [
            {"name": "Jane Traveler", "phone": "+15550199", "relationship": "Spouse"}
        ],
    })
    mock_db.users.docs.append({
        "id": "auth_1",
        "email": "operator@toursafe.dev",
        "role": "authority",
        "is_active": True,
    })

    monkeypatch.setattr(db_module, "get_database", lambda: mock_db)
    monkeypatch.setattr(auth_mod, "get_database", lambda: mock_db)
    return mock_db


@pytest.fixture
def tourist_token():
    return create_access_token("tourist_1", "tourist")


@pytest.fixture
def authority_token():
    return create_access_token("auth_1", "authority")


# ---------------------------------------------------------------------------
# 1. Manual SOS & Idempotency Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manual_sos_creation_and_idempotency(tourist_token, monkeypatch):
    # Mock live GPS lookup
    sample = LiveLocationResponse(
        tourist_id="tourist_1",
        location=LiveLocationPayload(
            latitude=10.2381,
            longitude=77.4892,
            accuracy=5.0,
            speed=1.2,
        ),
        timestamp=datetime.now(timezone.utc).isoformat(),
        staleness=LocationStaleness.LIVE,
    )
    monkeypatch.setattr(location_service, "get_live_location", AsyncMock(return_value=sample))

    headers = {"Authorization": f"Bearer {tourist_token}"}
    client_req_id = "req_test_abc_123"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First SOS transmission
        res1 = await client.post(
            "/api/v1/tourists/me/sos",
            headers=headers,
            json={
                "client_request_id": client_req_id,
                "reason": "Lost on trail",
                "category": "MEDICAL",
            },
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["status"] == "RECEIVED"
        assert data1["tourist_id"] == "tourist_1"
        assert data1["location_status"] == "CURRENT"
        assert data1["location"]["latitude"] == 10.2381
        sos_id = data1["sos_id"]
        incident_id = data1["incident_id"]

        # Second SOS transmission with IDENTICAL client_request_id (idempotent retry)
        res2 = await client.post(
            "/api/v1/tourists/me/sos",
            headers=headers,
            json={
                "client_request_id": client_req_id,
                "reason": "Lost on trail",
                "category": "MEDICAL",
            },
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["sos_id"] == sos_id
        assert data2["incident_id"] == incident_id

        # Check active SOS endpoint
        res_active = await client.get("/api/v1/tourists/me/sos/active", headers=headers)
        assert res_active.status_code == 200
        assert res_active.json()["active_sos"]["sos_id"] == sos_id

        # Cancel manual SOS
        res_cancel = await client.post(
            f"/api/v1/tourists/me/sos/{sos_id}/cancel",
            headers=headers,
            json={"reason": "Found the path, false alarm."},
        )
        assert res_cancel.status_code == 200
        assert res_cancel.json()["status"] == "CANCELLED"


# ---------------------------------------------------------------------------
# 2. Incident Command Lifecycle & State Machine Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_incident_lifecycle_and_transition_matrix(tourist_token, authority_token):
    tourist_headers = {"Authorization": f"Bearer {tourist_token}"}
    auth_headers = {"Authorization": f"Bearer {authority_token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Tourist triggers SOS -> Incident OPEN
        sos_res = await client.post(
            "/api/v1/tourists/me/sos",
            headers=tourist_headers,
            json={"client_request_id": "req_lifecycle_1", "reason": "Immediate danger"},
        )
        assert sos_res.status_code == 200
        inc_id = sos_res.json()["incident_id"]

        # Verify incident state is OPEN
        inc_get = await client.get(f"/api/v1/authority/incidents/{inc_id}", headers=auth_headers)
        assert inc_get.status_code == 200
        inc_data = inc_get.json()
        assert inc_data["status"] == "OPEN"
        assert inc_data["version"] == 1
        assert inc_data["source"] == "MANUAL_SOS"

        # 2. Authority Acknowledges Incident -> ACKNOWLEDGED
        ack_res = await client.post(
            f"/api/v1/authority/incidents/{inc_id}/acknowledge",
            headers=auth_headers,
            json={"notes": "Station 4 acknowledged, reviewing drone feed", "version": 1},
        )
        assert ack_res.status_code == 200
        assert ack_res.json()["status"] == "ACKNOWLEDGED"
        assert ack_res.json()["version"] == 2

        # Test Optimistic Locking: stale version should be rejected
        ack_stale = await client.post(
            f"/api/v1/authority/incidents/{inc_id}/acknowledge",
            headers=auth_headers,
            json={"notes": "Duplicate ack attempt", "version": 1},
        )
        assert ack_stale.status_code == 400
        assert "Optimistic lock conflict" in ack_stale.json()["detail"]

        # 3. Create Responder and Assign -> ASSIGNED
        resp_res = await client.post(
            "/api/v1/authority/responders",
            headers=auth_headers,
            json={
                "name": "Rapid Response Unit Alpha",
                "type": "FIELD_RESPONDER",
                "unit_id": "RRU-101",
                "capabilities": ["FIRST_AID", "MOUNTAIN_RESCUE"],
            },
        )
        assert resp_res.status_code == 200
        responder_id = resp_res.json()["responder_id"]

        assign_res = await client.post(
            f"/api/v1/authority/incidents/{inc_id}/assign",
            headers=auth_headers,
            json={"responder_id": responder_id, "notes": "Dispatched Alpha unit", "version": 2},
        )
        assert assign_res.status_code == 200
        assert assign_res.json()["status"] == "ASSIGNED"
        assert assign_res.json()["assigned_to"] == responder_id
        assert assign_res.json()["version"] == 3

        # 4. Responder starts response -> RESPONDING
        start_res = await client.post(
            f"/api/v1/authority/incidents/{inc_id}/response-start",
            headers=auth_headers,
            json={"estimated_arrival_minutes": 8, "notes": "En route via ATV", "version": 3},
        )
        assert start_res.status_code == 200
        assert start_res.json()["status"] == "RESPONDING"
        assert start_res.json()["version"] == 4

        # 5. Add Operational Note
        note_res = await client.post(
            f"/api/v1/authority/incidents/{inc_id}/notes",
            headers=auth_headers,
            json={"content": "Tourist located. Minor scratches, walking safely."},
        )
        assert note_res.status_code == 200

        # 6. Resolve Incident -> RESOLVED
        res_res = await client.post(
            f"/api/v1/authority/incidents/{inc_id}/resolve",
            headers=auth_headers,
            json={
                "resolution_reason": "Tourist escorted to trail base camp safely",
                "resolution_category": "TOURIST_SAFE",
                "notes": "Medical checks clear",
                "version": 5,
            },
        )
        assert res_res.status_code == 200
        assert res_res.json()["status"] == "RESOLVED"
        assert res_res.json()["resolution_category"] == "TOURIST_SAFE"
        assert res_res.json()["version"] == 6

        # 7. Close Incident -> CLOSED
        close_res = await client.post(
            f"/api/v1/authority/incidents/{inc_id}/close",
            headers=auth_headers,
            json={"notes": "Final report approved", "version": 6},
        )
        assert close_res.status_code == 200
        assert close_res.json()["status"] == "CLOSED"
        assert close_res.json()["closed_by"] == "auth_1"

        # 8. Verify Invalid Reopening: CLOSED -> OPEN must be rejected
        reopen_res = await client.post(
            f"/api/v1/authority/incidents/{inc_id}/acknowledge",
            headers=auth_headers,
            json={"notes": "Attempt to reopen"},
        )
        assert reopen_res.status_code == 400

        # 9. Verify Immutable Timeline
        timeline_res = await client.get(f"/api/v1/authority/incidents/{inc_id}/timeline", headers=auth_headers)
        assert timeline_res.status_code == 200
        events = timeline_res.json()
        actions = [e["action"] for e in events]
        assert "incident.created" in actions
        assert "incident.acknowledged" in actions
        assert "incident.assigned" in actions
        assert "incident.response.started" in actions
        assert "incident.note.added" in actions
        assert "incident.resolved" in actions
        assert "incident.closed" in actions


# ---------------------------------------------------------------------------
# 3. Durable Escalation Engine Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_durable_escalation_engine_and_idempotency():
    # Create an open incident that started 200 seconds ago (exceeding 120s acknowledgement timeout)
    old_start = (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat()
    inc = IncidentRecord(
        incident_id="inc_esc_test",
        tourist_id="tourist_1",
        started_at=old_start,
        status=IncidentStatus.OPEN,
        severity=IncidentSeverity.MEDIUM,
        source=IncidentSource.SAFETY_ENGINE,
        decision_id="dec_esc",
        rule_version="safety-rules-v1",
        reasons=["High risk zone dwell without motion"],
        version=1,
    )
    db = db_module.get_database()
    await db.incidents.insert_one(inc.model_dump())

    # Trigger escalation evaluation
    res1 = await escalation_engine.evaluate_incident_escalation(inc)
    assert res1 is not None
    assert res1["stage"] == 1
    assert inc.status == IncidentStatus.ESCALATED
    assert inc.severity == IncidentSeverity.HIGH

    # Second evaluation on same incident: Idempotent skip
    res2 = await escalation_engine.evaluate_incident_escalation(inc)
    assert res2 is None  # Already escalated for stage 1


# ---------------------------------------------------------------------------
# 4. Notification Abstraction & Emergency Contacts Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notification_service_and_emergency_contacts():
    # Test single notification attempt (defaults to NOT_CONFIGURED or SENT in test)
    rec = await notification_service.send_notification(
        recipient="+15550199",
        channel=NotificationChannel.SMS,
        subject="Test Alert",
        message="This is a test notification",
        incident_id="inc_notif_test",
    )
    assert rec.status in (NotificationStatus.SENT, NotificationStatus.NOT_CONFIGURED)
    assert rec.recipient == "+15550199"

    # Test emergency contact notifications for high-severity incident
    records = await notification_service.notify_emergency_contacts_for_incident(
        incident_id="inc_notif_test",
        tourist_id="tourist_1",
        severity="CRITICAL",
    )
    assert len(records) > 0
    rec_phones = [r.recipient for r in records]
    assert "+15550199" in rec_phones


# ---------------------------------------------------------------------------
# 5. Incident Metrics Endpoint Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_incident_command_metrics(authority_token):
    headers = {"Authorization": f"Bearer {authority_token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/authority/incidents/metrics", headers=headers)
        assert res.status_code == 200
        metrics = res.json()
        assert "total_incidents" in metrics
        assert "open_incidents" in metrics
        assert "resolved_incidents" in metrics
        assert "false_alarm_rate" in metrics
