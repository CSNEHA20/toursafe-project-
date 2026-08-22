import asyncio
import copy
from datetime import datetime, timezone
import os
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch

from app.main import app
import app.core.database as db_core
from app.core.security import create_access_token
from app.schemas.notification import (
    DeliveryErrorCategory,
    DevicePlatform,
    DeviceRegisterRequest,
    NotificationCategory,
    NotificationChannel,
    NotificationPayload,
    NotificationPriority,
    NotificationRecord,
    NotificationStatus,
    ProviderWebhookPayload,
    RecipientType,
    UserNotificationPreferences,
    UserPreferencesUpdateRequest,
)
from app.services.notifications import (
    NotificationCenterService,
    NotificationProvider,
    ProviderDeliveryResult,
    delivery_queue,
    dlq_service,
    emergency_policy,
    notification_center,
    policy_engine,
    provider_registry,
    recipient_resolver,
    retry_engine,
    template_engine,
)


class MockCollection:
    def __init__(self, name="collection"):
        self.name = name
        self.docs = []

    def _matches(self, doc, filter_dict):
        for k, v in filter_dict.items():
            if k == "$or":
                if not any(self._matches(doc, sub) for sub in v):
                    return False
            elif isinstance(v, dict):
                val = doc.get(k)
                if "$in" in v:
                    if val not in v["$in"]:
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

    async def find_one(self, filter_dict=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        matches = [d for d in self.docs if self._matches(d, filter_dict)]
        return copy.deepcopy(matches[0]) if matches else None

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

            async def to_list(self, length=100):
                return self.items[:length]

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index < len(self.items):
                    item = self.items[self.index]
                    self.index += 1
                    return item
                raise StopAsyncIteration

        return AsyncCursor(matches)

    async def update_one(self, filter_dict, update_dict, upsert=False, *args, **kwargs):
        filter_dict = filter_dict or {}
        set_vals = update_dict.get("$set", {})
        for d in self.docs:
            if self._matches(d, filter_dict):
                d.update(set_vals)
                return type("UpdateResult", (), {"matched_count": 1, "modified_count": 1})()
        if upsert:
            new_doc = copy.deepcopy(filter_dict)
            new_doc.update(set_vals)
            await self.insert_one(new_doc)
            return type("UpdateResult", (), {"matched_count": 0, "modified_count": 1, "upserted_id": new_doc.get("_id")})()
        return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0})()

    async def update_many(self, filter_dict, update_dict, *args, **kwargs):
        set_vals = update_dict.get("$set", {})
        count = 0
        for d in self.docs:
            if self._matches(d, filter_dict):
                d.update(set_vals)
                count += 1
        return type("UpdateResult", (), {"matched_count": count, "modified_count": count})()

    async def find_one_and_update(self, filter_dict, update_dict, return_document=True, *args, **kwargs):
        set_vals = update_dict.get("$set", {})
        for d in self.docs:
            if self._matches(d, filter_dict):
                d.update(set_vals)
                return copy.deepcopy(d)
        return None

    async def delete_one(self, filter_dict, *args, **kwargs):
        for i, d in enumerate(self.docs):
            if self._matches(d, filter_dict):
                del self.docs[i]
                return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()

    async def count_documents(self, filter_dict=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        return len([d for d in self.docs if self._matches(d, filter_dict)])


class MockDatabase:
    def __init__(self):
        self.notifications = MockCollection("notifications")
        self.notification_preferences = MockCollection("notification_preferences")
        self.notification_dead_letters = MockCollection("notification_dead_letters")
        self.device_tokens = MockCollection("device_tokens")
        self.communication_audits = MockCollection("communication_audits")
        self.provider_webhook_events = MockCollection("provider_webhook_events")
        self.users = MockCollection("users")
        self.tourists = MockCollection("tourists")
        self.responders = MockCollection("responders")
        self.responder_units = MockCollection("responder_units")
        self.emergency_contacts = MockCollection("emergency_contacts")
        self.incidents = MockCollection("incidents")

    async def command(self, cmd):
        return {"ok": 1.0}


@pytest.fixture(autouse=True)
def notif_mock_db_fixture(monkeypatch):
    os.environ["ENVIRONMENT"] = "test"
    mock_db = MockDatabase()
    monkeypatch.setattr(db_core, "get_database", lambda: mock_db)
    return mock_db


@pytest.fixture
def auth_headers():
    token = create_access_token("auth_user_001", "authority")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def tourist_headers():
    token = create_access_token("tourist_user_001", "tourist")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def responder_headers():
    token = create_access_token("responder_user_001", "responder")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Template Engine Tests & Security Sanitization
# ---------------------------------------------------------------------------

def test_template_engine_rendering_and_locales():
    # Test default English
    title, body = template_engine.render(
        template_id="incident-created-authority",
        variables={"incident_id": "INC-101", "severity": "CRITICAL", "zone_name": "Goa Beach North"},
        locale="en",
    )
    assert "INC-101" in title
    assert "CRITICAL" in body
    assert "Goa Beach North" in body

    # Test Spanish
    title_es, body_es = template_engine.render(
        template_id="incident-created-authority",
        variables={"incident_id": "INC-102", "severity": "CRITICAL", "zone_name": "Zona Norte"},
        locale="es",
    )
    assert "Alerta de Emergencia" in title_es
    assert "INC-102" in body_es

    # Test Hindi
    title_hi, body_hi = template_engine.render(
        template_id="sos-acknowledged-tourist",
        variables={},
        locale="hi",
    )
    assert "स्वीकृत" in title_hi

    # Test unknown locale fallback to English
    title_fb, _ = template_engine.render(
        template_id="sos-acknowledged-tourist",
        variables={},
        locale="xx_YY",
    )
    assert "SOS Acknowledged" in title_fb


def test_template_engine_security_sanitization():
    raw_vars = {
        "incident_id": "INC-999",
        "medical_history": "Cardiac arrhythmia",
        "medical_allergies": "Penicillin",
        "anomaly_score": 0.987654,
        "model_weights": "tensor([0.1, 0.2])",
        "latitude": 15.123456789,
        "longitude": 73.987654321,
    }
    sanitized = template_engine.sanitize_variables(raw_vars)

    assert "medical_history" not in sanitized
    assert "medical_allergies" not in sanitized
    assert "anomaly_score" not in sanitized
    assert "model_weights" not in sanitized
    assert sanitized["latitude"] == 15.1235
    assert sanitized["longitude"] == 73.9877


# ---------------------------------------------------------------------------
# 2. Policy Engine Tests
# ---------------------------------------------------------------------------

def test_policy_engine_evaluation():
    assert policy_engine.version == "notification-policy-v1"

    # Evaluate incident.created
    policies = policy_engine.evaluate_event("incident.created")
    assert len(policies) == 2

    auth_policy = next(p for p in policies if RecipientType.AUTHORITY in p.recipient_types)
    assert NotificationChannel.REALTIME in auth_policy.channels
    assert NotificationChannel.IN_APP in auth_policy.channels
    assert auth_policy.priority == NotificationPriority.CRITICAL
    assert auth_policy.is_mandatory is True

    # Evaluate incident.assigned
    assigned_policies = policy_engine.evaluate_event("incident.assigned")
    resp_policy = next(p for p in assigned_policies if RecipientType.RESPONDER in p.recipient_types)
    assert NotificationChannel.PUSH in resp_policy.channels
    assert resp_policy.is_mandatory is True


def test_emergency_policy_stages():
    stages = emergency_policy.get_stages_for_severity("CRITICAL")
    assert len(stages) >= 4

    stage_names = [s.name for s in stages]
    assert "IMMEDIATE_AUTHORITY_REALTIME" in stage_names
    assert "RESPONDER_PUSH_DISPATCH" in stage_names
    assert "EMERGENCY_CONTACT_SMS_EMAIL" in stage_names
    assert "HIGHER_AUTHORITY_ESCALATION" in stage_names


# ---------------------------------------------------------------------------
# 3. Recipient Resolution & Quiet Hours Overrides
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recipient_resolution_preferences_and_quiet_hours():
    # Normal optional notification inside quiet hours -> suppressed to IN_APP
    prefs = UserNotificationPreferences(
        user_id="user_test_qh",
        quiet_hours_enabled=True,
        quiet_hours_start="00:00",
        quiet_hours_end="23:59",  # active all day
    )
    req_channels = [NotificationChannel.PUSH, NotificationChannel.SMS, NotificationChannel.IN_APP]

    # Non-mandatory NORMAL notification
    filtered = recipient_resolver.filter_channels_by_preferences(
        req_channels, prefs, priority=NotificationPriority.NORMAL, is_mandatory=False
    )
    assert filtered == [NotificationChannel.IN_APP]

    # Mandatory CRITICAL notification MUST bypass quiet hours
    mandatory_filtered = recipient_resolver.filter_channels_by_preferences(
        req_channels, prefs, priority=NotificationPriority.CRITICAL, is_mandatory=True
    )
    assert set(mandatory_filtered) == set(req_channels)


# ---------------------------------------------------------------------------
# 4. Provider Abstractions & Honest Status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_provider_abstractions_and_health():
    statuses = await provider_registry.get_all_health_statuses()
    assert len(statuses) == 6

    channels = [s.channel for s in statuses]
    assert NotificationChannel.IN_APP in channels
    assert NotificationChannel.REALTIME in channels
    assert NotificationChannel.PUSH in channels
    assert NotificationChannel.SMS in channels
    assert NotificationChannel.EMAIL in channels
    assert NotificationChannel.VOICE in channels

    # Test SMS invalid phone validation
    sms_prov = provider_registry.get_provider(NotificationChannel.SMS)
    res_invalid_sms = await sms_prov.send(recipient="not_a_phone", subject="Hi", body="Test")
    assert res_invalid_sms.status == NotificationStatus.FAILED
    assert res_invalid_sms.error_category == DeliveryErrorCategory.INVALID_RECIPIENT

    # Test Email invalid email validation
    email_prov = provider_registry.get_provider(NotificationChannel.EMAIL)
    res_invalid_email = await email_prov.send(recipient="bad_email_at_com", subject="Hi", body="Test")
    assert res_invalid_email.status == NotificationStatus.FAILED
    assert res_invalid_email.error_category == DeliveryErrorCategory.INVALID_RECIPIENT

    # Test Push token invalidation simulation
    push_prov = provider_registry.get_provider(NotificationChannel.PUSH)
    res_invalid_push = await push_prov.send(
        recipient="token_expired_123", subject="Alert", body="Msg", metadata={"simulate_invalid_token": True}
    )
    assert res_invalid_push.status == NotificationStatus.FAILED
    assert res_invalid_push.error_category == DeliveryErrorCategory.INVALID_RECIPIENT


# ---------------------------------------------------------------------------
# 5. Retry Engine & Dead Letter Queue (DLQ)
# ---------------------------------------------------------------------------

def test_retry_engine_backoff_and_classification():
    # Permanent error should never be retried
    assert retry_engine.should_retry(attempt_count=1, error_category=DeliveryErrorCategory.PERMANENT) is False
    assert retry_engine.should_retry(attempt_count=1, error_category=DeliveryErrorCategory.INVALID_RECIPIENT) is False

    # Transient error should be retried within limit
    assert retry_engine.should_retry(attempt_count=1, error_category=DeliveryErrorCategory.TRANSIENT) is True
    assert retry_engine.should_retry(attempt_count=3, error_category=DeliveryErrorCategory.TRANSIENT) is False

    # Backoff calculation increases
    d1 = retry_engine.calculate_backoff_delay(1)
    d2 = retry_engine.calculate_backoff_delay(2)
    assert d2 >= d1 * 0.8  # accounts for jitter


@pytest.mark.asyncio
async def test_dead_letter_queue_operations():
    notif = NotificationRecord(
        recipient_id="tourist_999",
        recipient_type=RecipientType.TOURIST,
        channel=NotificationChannel.SMS,
        priority=NotificationPriority.CRITICAL,
        idempotency_key="test_dlq_key_1",
        payload=NotificationPayload(title="SOS Failed", body="Delivery exhausted"),
        retry_count=3,
        error_code="CARRIER_UNREACHABLE",
        error_message="SMS gateway dropped connection",
    )

    dlq_rec = await dlq_service.enqueue_dead_letter(
        notification=notif,
        reason="Exhausted 3 retry attempts",
        last_error_code="CARRIER_UNREACHABLE",
        last_error_message="SMS gateway dropped connection",
        last_error_category=DeliveryErrorCategory.TRANSIENT,
    )
    assert dlq_rec.dead_letter_id.startswith("dlq_")
    assert dlq_rec.resolved is False

    # List dead letters
    dlq_list = await dlq_service.list_dead_letters(limit=10, unresolved_only=True)
    assert any(d.dead_letter_id == dlq_rec.dead_letter_id for d in dlq_list)

    # Admin resolves / retries dead letter
    resolved = await dlq_service.resolve_dead_letter(
        dead_letter_id=dlq_rec.dead_letter_id,
        action="RETRIED",
        resolved_by="admin_user_1",
        notes="Manual retry after carrier recovery",
    )
    assert resolved is not None
    assert resolved.resolved is True
    assert resolved.resolution_action == "RETRIED"


# ---------------------------------------------------------------------------
# 6. Idempotency Key Deduplication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_idempotency_key_deduplication():
    event_id = "evt_idempotency_test_001"
    key = delivery_queue.generate_idempotency_key(
        event_id=event_id,
        recipient_id="user_alpha",
        channel=NotificationChannel.IN_APP,
    )

    notif1 = NotificationRecord(
        event_id=event_id,
        recipient_id="user_alpha",
        channel=NotificationChannel.IN_APP,
        idempotency_key=key,
        payload=NotificationPayload(title="Alert 1", body="Message 1"),
    )
    saved1 = await delivery_queue.enqueue(notif1)
    assert saved1.status == NotificationStatus.DELIVERED

    # Attempt to enqueue second notification with duplicate idempotency key
    notif2 = NotificationRecord(
        event_id=event_id,
        recipient_id="user_alpha",
        channel=NotificationChannel.IN_APP,
        idempotency_key=key,
        payload=NotificationPayload(title="Alert Duplicate", body="Message Duplicate"),
    )
    saved2 = await delivery_queue.enqueue(notif2)
    # Must return original notification record without creating a duplicate
    assert saved2.notification_id == saved1.notification_id


# ---------------------------------------------------------------------------
# 7. Webhook Delivery Receipt Processing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_provider_webhook_processing():
    notif = NotificationRecord(
        recipient_id="user_webhook_test",
        channel=NotificationChannel.SMS,
        idempotency_key="webhook_test_key_1",
        provider_message_id="msg_twilio_receipt_101",
        payload=NotificationPayload(title="SMS Alert", body="Details"),
        status=NotificationStatus.SENT,
    )
    db = db_core.get_database()
    await db.notifications.insert_one(notif.model_dump())

    webhook = ProviderWebhookPayload(
        provider="twilio",
        provider_event_id="evt_twilio_001",
        provider_message_id="msg_twilio_receipt_101",
        status="delivered",
    )
    res = await notification_center.process_provider_webhook(webhook)
    assert res["status"] == "PROCESSED"
    assert res["notification_status"] == "DELIVERED"

    # Verify idempotency on second receipt with same provider_event_id
    res_dup = await notification_center.process_provider_webhook(webhook)
    assert res_dup["status"] == "SKIPPED"


# ---------------------------------------------------------------------------
# 8. Notification REST API Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notifications_api_endpoints(auth_headers, tourist_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Device Registration
        dev_res = await client.post(
            "/api/v1/devices/register",
            json={"token": "fcm_token_test_12345", "platform": "ANDROID", "app_version": "1.0.0"},
            headers=tourist_headers,
        )
        assert dev_res.status_code == 200
        dev_data = dev_res.json()
        assert dev_data["token"] == "fcm_token_test_12345"

        # 2. Get User Notifications
        notif_res = await client.get("/api/v1/notifications", headers=tourist_headers)
        assert notif_res.status_code == 200
        assert isinstance(notif_res.json(), list)

        # 3. Get Unread Count
        unread_res = await client.get("/api/v1/notifications/unread-count", headers=tourist_headers)
        assert unread_res.status_code == 200
        assert "unread_count" in unread_res.json()

        # 4. Preferences Get & Update
        pref_get = await client.get("/api/v1/notifications/preferences", headers=tourist_headers)
        assert pref_get.status_code == 200

        pref_patch = await client.patch(
            "/api/v1/notifications/preferences",
            json={"quiet_hours_enabled": True, "quiet_hours_start": "23:00", "quiet_hours_end": "06:00"},
            headers=tourist_headers,
        )
        assert pref_patch.status_code == 200
        assert pref_patch.json()["quiet_hours_enabled"] is True

        # 5. Admin Provider Health API
        prov_health = await client.get("/api/v1/admin/notifications/providers", headers=auth_headers)
        assert prov_health.status_code == 200
        assert len(prov_health.json()) == 6

        # 6. Admin Metrics API
        metrics_res = await client.get("/api/v1/notifications/metrics", headers=auth_headers)
        assert metrics_res.status_code == 200
        assert "total_notifications" in metrics_res.json()


# ---------------------------------------------------------------------------
# 9. End-to-End Incident & SOS Notification Flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_end_to_end_incident_and_sos_notification_lifecycle():
    # 1. Trigger incident.created
    incident_payload = {
        "incident_id": "INC-E2E-100",
        "tourist_id": "tourist_e2e_user",
        "severity": "HIGH",
        "zone_name": "Calangute Security Zone",
        "reason": "SOS Panic Triggered",
        "tourist_name": "Jane Doe",
    }

    records = await notification_center.handle_domain_event(
        event_type="incident.created",
        payload=incident_payload,
        incident_id="INC-E2E-100",
        tourist_id="tourist_e2e_user",
    )
    assert len(records) >= 2

    # Check authority notification
    auth_notif = next((r for r in records if r.recipient_type == RecipientType.AUTHORITY), None)
    assert auth_notif is not None
    assert auth_notif.priority == NotificationPriority.CRITICAL

    # Check tourist notification
    tourist_notif = next((r for r in records if r.recipient_type == RecipientType.TOURIST), None)
    assert tourist_notif is not None
    assert "SOS Acknowledged" in tourist_notif.payload.title

    # 2. Trigger incident.assigned
    assign_payload = {
        "incident_id": "INC-E2E-100",
        "tourist_id": "tourist_e2e_user",
        "assigned_responder_id": "resp_alpha_01",
        "severity": "HIGH",
        "zone_name": "Calangute Security Zone",
    }
    assign_records = await notification_center.handle_domain_event(
        event_type="incident.assigned",
        payload=assign_payload,
        incident_id="INC-E2E-100",
        responder_id="resp_alpha_01",
    )
    assert len(assign_records) >= 1

    # 3. Trigger incident.resolved
    resolve_payload = {
        "incident_id": "INC-E2E-100",
        "tourist_id": "tourist_e2e_user",
        "resolution_reason": "Responder arrived and provided first aid",
    }
    resolve_records = await notification_center.handle_domain_event(
        event_type="incident.resolved",
        payload=resolve_payload,
        incident_id="INC-E2E-100",
        tourist_id="tourist_e2e_user",
    )
    assert len(resolve_records) >= 1
    t_resolve = next((r for r in resolve_records if r.recipient_type == RecipientType.TOURIST), None)
    assert t_resolve is not None
    assert "Incident Resolved" in t_resolve.payload.title
