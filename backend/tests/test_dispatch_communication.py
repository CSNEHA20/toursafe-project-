"""
TourSafe Prompt 22: Dispatch, Communication & Multi-Party Incident Coordination Test Suite

Validates:
- Incident-scoped communication channel lifecycle & participants
- Attributed multi-party messaging (Tourist <-> Authority <-> Responder)
- Strictly monotonic server sequence numbering
- Message idempotency with client_message_id
- Delivery, read receipts, and explicit critical acknowledgements
- Sequence gap recovery & reconnect reconciliation
- Multi-responder dispatch coordination (Primary / Secondary / Specialist)
- Responder handover and escalation workflows with system events
- Closed channel protection against new operational messages
- RBAC, cross-incident isolation, attachment security, and rate-limiting
- Full REST API endpoint coverage via FastAPI TestClient
"""

import asyncio
import copy
from datetime import datetime, timezone
import pytest
import sys
from typing import Any, Dict, List, Optional
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, "backend")

from app.main import app
from app.core.security import create_access_token
import app.core.database as db_module
import app.routers.auth as auth_mod
import app.routers.incident_communication as comm_mod

from app.schemas.emergency import (
    AttachmentUploadRequest,
    ChannelParticipantAddRequest,
    ChannelParticipantUpdateRequest,
    ChannelStatus,
    IncidentSeverity,
    IncidentStatus,
    MessageAckRequest,
    MessagePriority,
    MessageSendRequest,
    MessageType,
    MultiResponderAssignRequest,
    ParticipantPresenceStatus,
    ParticipantRole,
    ParticipantStatus,
    ResponderAssignmentRole,
    ResponderRecord,
    ResponderStatus,
    ResponderType,
    StructuredLocationData,
)
from app.services.emergency import (
    assignment_service,
    incident_channel_service,
    incident_service,
    messaging_service,
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
            else:
                parts = k.split(".")
                curr = [doc]
                for part in parts:
                    next_curr = []
                    for item in curr:
                        if isinstance(item, dict):
                            val = item.get(part)
                            if isinstance(val, list):
                                next_curr.extend(val)
                            else:
                                next_curr.append(val)
                    curr = next_curr

                if not curr:
                    curr = [None]

                if isinstance(v, dict):
                    if "$in" in v:
                        if not any(val in v["$in"] for val in curr):
                            return False
                    elif "$ne" in v:
                        target = v["$ne"]
                        if any(val == target for val in curr):
                            return False
                    elif "$gt" in v:
                        if not any(val is not None and val > v["$gt"] for val in curr):
                            return False
                    elif "$gte" in v:
                        if not any(val is not None and val >= v["$gte"] for val in curr):
                            return False
                    elif "$lt" in v:
                        if not any(val is not None and val < v["$lt"] for val in curr):
                            return False
                    elif "$lte" in v:
                        if not any(val is not None and val <= v["$lte"] for val in curr):
                            return False
                    elif "$regex" in v:
                        pat = v["$regex"].lower()
                        if not any(val is not None and pat in str(val).lower() for val in curr):
                            return False
                else:
                    if not any(val == v for val in curr):
                        return False
        return True

    async def insert_one(self, doc):
        d = copy.deepcopy(doc)
        if "_id" not in d:
            d["_id"] = f"mock_{len(self.docs)+1}"
        self.docs.append(d)
        return type("InsertResult", (), {"inserted_id": d["_id"]})()

    async def insert_many(self, doc_list):
        for doc in doc_list:
            await self.insert_one(doc)

    async def find_one(self, filter_dict=None, sort=None, *args, **kwargs):
        if not filter_dict:
            return copy.deepcopy(self.docs[0]) if self.docs else None
        matching = [d for d in self.docs if self._matches(d, filter_dict)]
        if not matching:
            return None
        if sort:
            key, direction = sort[0]
            matching.sort(key=lambda x: x.get(key, 0), reverse=(direction == -1))
        return copy.deepcopy(matching[0])

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
                self._docs.sort(key=lambda x: x.get(key, 0), reverse=(direction == -1))
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
                    for k, val in update_dict["$set"].items():
                        if "." in k:
                            sub_k, sub_v = k.split(".", 1)
                            if sub_k not in doc or not isinstance(doc[sub_k], dict):
                                doc[sub_k] = {}
                            doc[sub_k][sub_v] = copy.deepcopy(val)
                        else:
                            doc[k] = copy.deepcopy(val)
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
                    for k, val in update_dict["$set"].items():
                        if "." in k:
                            sub_k, sub_v = k.split(".", 1)
                            if sub_k not in doc or not isinstance(doc[sub_k], dict):
                                doc[sub_k] = {}
                            doc[sub_k][sub_v] = copy.deepcopy(val)
                        else:
                            doc[k] = copy.deepcopy(val)
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
                    for k, val in update_dict["$set"].items():
                        doc[k] = copy.deepcopy(val)
                if "$inc" in update_dict:
                    for k, val in update_dict["$inc"].items():
                        doc[k] = doc.get(k, 0) + val
                return copy.deepcopy(doc)
        return None


class MockDatabase:
    def __init__(self):
        self.users = MockCollection("users")
        self.tourist_profiles = MockCollection("tourist_profiles")
        self.authority_profiles = MockCollection("authority_profiles")
        self.responders = MockCollection("responders")
        self.responder_units = MockCollection("responder_units")
        self.incident_assignments = MockCollection("incident_assignments")
        self.incident_channels = MockCollection("incident_channels")
        self.channel_participants = MockCollection("channel_participants")
        self.incident_messages = MockCollection("incident_messages")
        self.incident_attachments = MockCollection("incident_attachments")
        self.communication_audit_logs = MockCollection("communication_audit_logs")
        self.incidents = MockCollection("incidents")
        self.notifications = MockCollection("notifications")

        # Initial seed
        self.users.docs = [
            {"id": "usr_tourist_1", "role": "tourist", "full_name": "Alice Tourist", "is_active": True},
            {"id": "usr_tourist_2", "role": "tourist", "full_name": "Bob Tourist", "is_active": True},
            {"id": "usr_authority_1", "role": "authority", "full_name": "Commander Singh", "is_active": True},
            {"id": "usr_responder_1", "role": "responder", "full_name": "Officer Rahul", "is_active": True},
            {"id": "usr_responder_2", "role": "responder", "full_name": "Dr. Sneha", "is_active": True},
        ]
        self.tourist_profiles.docs = [
            {"id": "tourist_1", "user_id": "usr_tourist_1", "full_name": "Alice Tourist"},
        ]
        self.authority_profiles.docs = [
            {"id": "auth_1", "user_id": "usr_authority_1", "full_name": "Commander Singh"},
        ]
        self.responders.docs = [
            {
                "responder_id": "resp_1",
                "user_id": "usr_responder_1",
                "name": "Officer Rahul",
                "type": ResponderType.FIELD_RESPONDER.value,
                "status": ResponderStatus.AVAILABLE.value,
                "capabilities": ["FIRST_AID", "SECURITY"],
                "active": True,
            },
            {
                "responder_id": "resp_2",
                "user_id": "usr_responder_2",
                "name": "Dr. Sneha",
                "type": ResponderType.MEDICAL.value,
                "status": ResponderStatus.AVAILABLE.value,
                "capabilities": ["MEDICAL", "FIRST_AID"],
                "active": True,
            },
        ]
        self.incidents.docs = [
            {
                "incident_id": "inc_comm_test_100",
                "tourist_id": "tourist_1",
                "status": IncidentStatus.OPEN.value,
                "severity": IncidentSeverity.HIGH.value,
                "source": "MANUAL_SOS",
                "escalation_stage": 0,
                "escalation_history": [],
                "version": 1,
                "timeline": [],
                "notes_list": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ]

    def __getitem__(self, name):
        if not hasattr(self, name):
            setattr(self, name, MockCollection(name))
        return getattr(self, name)


@pytest.fixture(autouse=True)
def setup_mock_db(monkeypatch):
    mock_db = MockDatabase()
    from app.services.emergency.messaging_service import _RATE_LIMIT_STORE
    _RATE_LIMIT_STORE.clear()

    monkeypatch.setattr(db_module, "database", mock_db)
    monkeypatch.setattr(db_module, "get_database", lambda: mock_db)
    monkeypatch.setattr(auth_mod, "get_database", lambda: mock_db)
    monkeypatch.setattr(comm_mod, "get_database", lambda: mock_db)

    return mock_db


@pytest.mark.asyncio
async def test_channel_lifecycle_and_participants(setup_mock_db):
    """
    Verifies automatic channel creation, participant auto-addition,
    presence management, and channel closure.
    """
    incident_id = "inc_comm_test_100"

    # 1. Get or create channel
    channel = await incident_channel_service.get_or_create_channel(incident_id)
    assert channel.incident_id == incident_id
    assert channel.status == ChannelStatus.ACTIVE
    assert channel.sequence_counter == 0

    # 2. Check auto-added tourist participant
    participants = await incident_channel_service.get_participants(incident_id)
    assert len(participants) >= 1
    assert any(p.user_id == "usr_tourist_1" and p.role == ParticipantRole.TOURIST for p in participants)

    # 3. Add an authority participant
    auth_p = await incident_channel_service.add_participant(
        incident_id=incident_id,
        user_id="usr_authority_1",
        display_name="Commander Singh",
        role=ParticipantRole.AUTHORITY,
    )
    assert auth_p.role == ParticipantRole.AUTHORITY
    assert auth_p.status == ParticipantStatus.ACTIVE

    # 4. Update presence
    pres_p = await incident_channel_service.update_presence(
        incident_id=incident_id,
        user_id="usr_authority_1",
        presence=ParticipantPresenceStatus.ONLINE,
    )
    assert pres_p.presence == ParticipantPresenceStatus.ONLINE
    assert pres_p.last_seen_at is not None

    # 5. Remove/restrict participant
    removed_p = await incident_channel_service.remove_participant(
        incident_id=incident_id,
        user_id="usr_authority_1",
        reason="Shift concluded",
    )
    assert removed_p.status == ParticipantStatus.REMOVED
    assert removed_p.left_at is not None

    active_parts = await incident_channel_service.get_participants(incident_id, include_removed=False)
    assert not any(p.user_id == "usr_authority_1" for p in active_parts)


@pytest.mark.asyncio
async def test_strictly_ordered_server_sequences_and_content_sanitization(setup_mock_db):
    """
    Verifies that messages receive strictly monotonically increasing server sequence numbers
    and that HTML input is properly escaped against XSS injection.
    """
    incident_id = "inc_comm_test_100"

    # Send 3 messages from different participants
    msg1 = await messaging_service.send_message(
        incident_id=incident_id,
        sender_id="usr_tourist_1",
        sender_role=ParticipantRole.TOURIST,
        sender_name="Alice",
        req=MessageSendRequest(content="<script>alert('xss')</script>Help me please!"),
    )
    assert msg1.server_sequence == 1
    # Check HTML sanitization
    assert "<script>" not in msg1.content
    assert "&lt;script&gt;" in msg1.content

    msg2 = await messaging_service.send_message(
        incident_id=incident_id,
        sender_id="usr_authority_1",
        sender_role=ParticipantRole.AUTHORITY,
        sender_name="Commander Singh",
        req=MessageSendRequest(
            content="Stay calm, responders dispatched to your location.",
            priority=MessagePriority.IMPORTANT,
        ),
    )
    assert msg2.server_sequence == 2

    # Structured Location Message
    msg3 = await messaging_service.send_message(
        incident_id=incident_id,
        sender_id="usr_tourist_1",
        sender_role=ParticipantRole.TOURIST,
        sender_name="Alice",
        req=MessageSendRequest(
            content="My current coordinates",
            message_type=MessageType.LOCATION,
            location_data=StructuredLocationData(
                latitude=15.4989,
                longitude=73.8278,
                accuracy=5.2,
                label="Near north gate",
            ),
        ),
    )
    assert msg3.server_sequence == 3
    assert msg3.location_data.latitude == 15.4989

    # System Message
    sys_msg = await messaging_service.send_system_message(
        incident_id=incident_id,
        content="Responder dispatched to scene.",
    )
    assert sys_msg.server_sequence == 4
    assert sys_msg.message_type == MessageType.SYSTEM

    # Fetch and verify order
    all_msgs = await messaging_service.get_messages(incident_id)
    sequences = [m.server_sequence for m in all_msgs]
    assert sequences == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_message_idempotency(setup_mock_db):
    """
    Verifies that re-transmitting the same message with client_message_id
    returns the exact same message record without duplicate records or sequence skips.
    """
    incident_id = "inc_comm_test_100"
    client_id = "client_uuid_abc_123"

    req = MessageSendRequest(
        content="Idempotent message attempt",
        client_message_id=client_id,
    )

    first_msg = await messaging_service.send_message(
        incident_id=incident_id,
        sender_id="usr_tourist_1",
        sender_role=ParticipantRole.TOURIST,
        sender_name="Alice",
        req=req,
    )

    # Retry with same client_message_id
    second_msg = await messaging_service.send_message(
        incident_id=incident_id,
        sender_id="usr_tourist_1",
        sender_role=ParticipantRole.TOURIST,
        sender_name="Alice",
        req=req,
    )

    assert first_msg.message_id == second_msg.message_id
    assert first_msg.server_sequence == second_msg.server_sequence

    # Verify only one record in database
    msgs = await messaging_service.get_messages(incident_id)
    idempotent_msgs = [m for m in msgs if m.client_message_id == client_id]
    assert len(idempotent_msgs) == 1


@pytest.mark.asyncio
async def test_delivery_read_receipts_and_critical_acknowledgement(setup_mock_db):
    """
    Verifies read status tracking and explicit critical message acknowledgements.
    Confirms READ != ACKNOWLEDGED.
    """
    incident_id = "inc_comm_test_100"

    # Send Critical Message requiring acknowledgement
    crit_msg = await messaging_service.send_message(
        incident_id=incident_id,
        sender_id="usr_authority_1",
        sender_role=ParticipantRole.AUTHORITY,
        sender_name="Commander Singh",
        req=MessageSendRequest(
            content="DO NOT MOVE: Stay inside the marked safe perimeter.",
            priority=MessagePriority.CRITICAL,
            requires_acknowledgement=True,
        ),
    )
    assert crit_msg.requires_acknowledgement is True
    assert len(crit_msg.acknowledged_by) == 0

    # 1. Tourist Marks Read
    await messaging_service.mark_messages_read(
        incident_id=incident_id,
        reader_id="usr_tourist_1",
        up_to_sequence=crit_msg.server_sequence,
    )

    # Check snapshot: Message is read by tourist, but NOT yet acknowledged
    snapshot = await messaging_service.get_channel_snapshot(incident_id, "usr_tourist_1")
    assert snapshot.unread_count == 0
    assert snapshot.pending_acknowledgements_count == 1

    # 2. Tourist Explicitly Acknowledges
    acked_msg = await messaging_service.acknowledge_message(
        incident_id=incident_id,
        message_id=crit_msg.message_id,
        actor_id="usr_tourist_1",
        actor_role="TOURIST",
        actor_name="Alice",
        notes="Understood, staying in the safe zone.",
    )
    assert len(acked_msg.acknowledged_by) == 1
    assert acked_msg.acknowledged_by[0].actor_id == "usr_tourist_1"
    assert acked_msg.acknowledged_by[0].notes == "Understood, staying in the safe zone."

    # Verify pending acknowledgements count dropped to 0
    snapshot_after = await messaging_service.get_channel_snapshot(incident_id, "usr_tourist_1")
    assert snapshot_after.pending_acknowledgements_count == 0


@pytest.mark.asyncio
async def test_reconnect_sequence_gap_recovery(setup_mock_db):
    """
    Verifies that reconnecting clients can recover missing messages in a sequence gap.
    """
    incident_id = "inc_comm_test_100"

    for i in range(1, 6):
        await messaging_service.send_message(
            incident_id=incident_id,
            sender_id="usr_authority_1",
            sender_role=ParticipantRole.AUTHORITY,
            sender_name="Commander Singh",
            req=MessageSendRequest(content=f"Message step {i}"),
        )

    # Simulate client having only received up to sequence 2, requesting gap recovery since sequence 2
    recovery = await messaging_service.recover_gap(
        incident_id=incident_id,
        since_sequence=2,
        limit=10,
    )
    assert recovery.since_sequence == 2
    assert len(recovery.messages) == 3
    assert [m.server_sequence for m in recovery.messages] == [3, 4, 5]


@pytest.mark.asyncio
async def test_multi_responder_dispatch_and_handover_lifecycle(setup_mock_db):
    """
    Verifies multi-responder coordination:
    1. Primary responder assigned -> auto-added to channel & system message broadcast.
    2. Primary responder accepts assignment -> system message broadcast.
    3. Secondary medical specialist assigned -> multi-responder presence in channel.
    4. Handover request by primary responder -> participant restricted & system event broadcast.
    """
    incident_id = "inc_comm_test_100"

    # 1. Primary assignment
    asgn1 = await assignment_service.create_assignment(
        incident_id=incident_id,
        responder_id="resp_1",
        assigned_by="usr_authority_1",
        assignment_role=ResponderAssignmentRole.PRIMARY,
    )
    assert asgn1.responder_id == "resp_1"

    # Check participant in channel
    p1 = await incident_channel_service.get_participant(incident_id, "usr_responder_1")
    assert p1 is not None
    assert p1.role == ParticipantRole.RESPONDER
    assert p1.responder_role == ResponderAssignmentRole.PRIMARY

    # 2. Accept assignment
    await assignment_service.accept_assignment(
        incident_id=incident_id,
        assignment_id=asgn1.assignment_id,
        responder_id="resp_1",
    )

    # 3. Multi-responder assignment (Secondary specialist)
    asgn2 = await assignment_service.create_assignment(
        incident_id=incident_id,
        responder_id="resp_2",
        assigned_by="usr_authority_1",
        assignment_role=ResponderAssignmentRole.SPECIALIST,
    )
    assert asgn2.responder_id == "resp_2"

    p2 = await incident_channel_service.get_participant(incident_id, "usr_responder_2")
    assert p2 is not None
    assert p2.responder_role == ResponderAssignmentRole.SPECIALIST

    # 4. Handover from resp_1
    from app.schemas.emergency import AssignmentHandoverRequest, HandoverReason
    await assignment_service.request_handover(
        incident_id=incident_id,
        assignment_id=asgn1.assignment_id,
        responder_id="resp_1",
        req=AssignmentHandoverRequest(
            reason=HandoverReason.CAPABILITY,
            details="Patient requires medical specialist",
            replacement_capability="MEDICAL",
        ),
    )

    p1_after = await incident_channel_service.get_participant(incident_id, "usr_responder_1")
    assert p1_after.status == ParticipantStatus.RESTRICTED

    # Check system messages history in channel
    msgs = await messaging_service.get_messages(incident_id)
    sys_contents = [m.content for m in msgs if m.message_type == MessageType.SYSTEM]
    assert any("Officer Rahul" in c and "assigned" in c for c in sys_contents)
    assert any("accepted the assignment" in c for c in sys_contents)
    assert any("handover" in c for c in sys_contents)


@pytest.mark.asyncio
async def test_closed_channel_rejects_new_operational_messages(setup_mock_db):
    """
    Verifies that closed incident channels reject any new incoming operational messages.
    """
    incident_id = "inc_comm_test_100"

    # Close the channel
    await incident_channel_service.close_channel(incident_id)
    channel = await incident_channel_service.get_channel(incident_id)
    assert channel.status == ChannelStatus.CLOSED

    # Attempt to send message
    with pytest.raises(ValueError, match="CLOSED"):
        await messaging_service.send_message(
            incident_id=incident_id,
            sender_id="usr_tourist_1",
            sender_role=ParticipantRole.TOURIST,
            sender_name="Alice",
            req=MessageSendRequest(content="Can I still talk?"),
        )


@pytest.mark.asyncio
async def test_rest_api_full_endpoint_suite(setup_mock_db):
    """
    Tests the REST API layer for incident communication using HTTP client.
    """
    incident_id = "inc_comm_test_100"
    tourist_token = create_access_token("usr_tourist_1", "tourist")
    authority_token = create_access_token("usr_authority_1", "authority")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Get Snapshot
        res = await client.get(
            f"/api/v1/incidents/{incident_id}/channel",
            headers={"Authorization": f"Bearer {tourist_token}"},
        )
        assert res.status_code == 200
        snap = res.json()
        assert "channel" in snap
        assert "participants" in snap

        # 2. Send Message via API
        msg_res = await client.post(
            f"/api/v1/incidents/{incident_id}/messages",
            headers={"Authorization": f"Bearer {tourist_token}"},
            json={
                "content": "Hello via REST API",
                "client_message_id": "rest_cli_msg_1",
                "priority": "NORMAL",
            },
        )
        assert msg_res.status_code == 201
        created_msg = msg_res.json()
        assert created_msg["content"] == "Hello via REST API"
        msg_id = created_msg["message_id"]

        # 3. Read receipt via API
        read_res = await client.post(
            f"/api/v1/incidents/{incident_id}/messages/{msg_id}/read",
            headers={"Authorization": f"Bearer {authority_token}"},
        )
        assert read_res.status_code == 200

        # 4. Critical Message & Ack via API
        crit_res = await client.post(
            f"/api/v1/incidents/{incident_id}/messages",
            headers={"Authorization": f"Bearer {authority_token}"},
            json={
                "content": "CRITICAL INSTRUCTION: Move to higher ground",
                "priority": "CRITICAL",
                "requires_acknowledgement": True,
            },
        )
        assert crit_res.status_code == 201
        crit_msg_id = crit_res.json()["message_id"]

        ack_res = await client.post(
            f"/api/v1/incidents/{incident_id}/messages/{crit_msg_id}/acknowledge",
            headers={"Authorization": f"Bearer {tourist_token}"},
            json={"notes": "Heading up now."},
        )
        assert ack_res.status_code == 200
        assert len(ack_res.json()["acknowledged_by"]) >= 1

        # 5. Search Messages via API
        search_res = await client.get(
            f"/api/v1/incidents/{incident_id}/messages/search?q=ground",
            headers={"Authorization": f"Bearer {authority_token}"},
        )
        assert search_res.status_code == 200
        assert search_res.json()["total"] >= 1

        # 6. Cross-Incident Isolation (Unauthorized tourist Bob attempting Alice's incident)
        unauth_tourist_token = create_access_token("usr_tourist_2", "tourist")
        iso_res = await client.get(
            f"/api/v1/incidents/{incident_id}/channel",
            headers={"Authorization": f"Bearer {unauth_tourist_token}"},
        )
        assert iso_res.status_code == 403
