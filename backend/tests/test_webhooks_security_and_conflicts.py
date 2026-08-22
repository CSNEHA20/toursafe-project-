from datetime import datetime, timezone
import json
import pytest
from app.schemas.integrations import IntegrationType
from app.services.integrations.conflict_resolver import ExternalConflictService
from app.services.integrations.dead_letter import DeadLetterQueueService
from app.services.integrations.events import OutboundEventPublisher
from app.services.integrations.security import SecurityManager, SSRFProtectionException
from app.services.integrations.webhooks import WebhookManager, WebhookVerificationException


@pytest.mark.asyncio
async def test_01_webhook_valid_hmac_signature():
    mgr = WebhookManager()
    secret = "test_webhook_secret_key"
    payload = {"event_id": "evt_wh_001", "event_type": "KYC_VERIFIED", "tourist_id": "T-101"}
    raw_body = json.dumps(payload).encode("utf-8")

    sig = OutboundEventPublisher.create_signature(raw_body.decode("utf-8"), secret)
    headers = {
        "x-signature-256": sig,
        "x-webhook-id": "evt_wh_001",
        "x-webhook-timestamp": datetime.now(timezone.utc).isoformat(),
    }

    res = await mgr.process_inbound_webhook(
        provider_type="IDENTITY",
        provider_name="DEV_KYC_PROVIDER",
        raw_body=raw_body,
        headers=headers,
        secret=secret,
    )
    assert res.success is True
    assert res.duplicate is False
    assert res.event_id == "evt_wh_001"


@pytest.mark.asyncio
async def test_02_webhook_invalid_signature_rejection():
    mgr = WebhookManager()
    secret = "test_webhook_secret_key"
    payload = {"event_id": "evt_wh_002", "event_type": "KYC_VERIFIED"}
    raw_body = json.dumps(payload).encode("utf-8")

    headers = {
        "x-signature-256": "invalid_tampered_signature_hex",
        "x-webhook-id": "evt_wh_002",
        "x-webhook-timestamp": datetime.now(timezone.utc).isoformat(),
    }

    with pytest.raises(WebhookVerificationException):
        await mgr.process_inbound_webhook(
            provider_type="IDENTITY",
            provider_name="DEV_KYC_PROVIDER",
            raw_body=raw_body,
            headers=headers,
            secret=secret,
        )


@pytest.mark.asyncio
async def test_03_webhook_stale_timestamp_rejection():
    mgr = WebhookManager()
    secret = "test_webhook_secret_key"
    payload = {"event_id": "evt_wh_003", "event_type": "CAD_STATUS_UPDATE"}
    raw_body = json.dumps(payload).encode("utf-8")

    sig = OutboundEventPublisher.create_signature(raw_body.decode("utf-8"), secret)
    # Stale timestamp: 1 hour ago
    headers = {
        "x-signature-256": sig,
        "x-webhook-id": "evt_wh_003",
        "x-webhook-timestamp": "2026-08-22T10:00:00+00:00",
    }

    with pytest.raises(WebhookVerificationException) as exc:
        await mgr.process_inbound_webhook(
            provider_type="EMERGENCY_SERVICE",
            provider_name="DEV_EMERGENCY_CAD",
            raw_body=raw_body,
            headers=headers,
            secret=secret,
        )
    assert "outside acceptable window" in str(exc.value)


@pytest.mark.asyncio
async def test_04_ssrf_protection():
    sec = SecurityManager()

    # Block localhost
    with pytest.raises(SSRFProtectionException):
        sec.validate_outbound_url("http://localhost:8080/internal-admin")

    # Block 127.0.0.1 loopback
    with pytest.raises(SSRFProtectionException):
        sec.validate_outbound_url("http://127.0.0.1:9000/keys")

    # Block Private RFC1918 (192.168.1.10)
    with pytest.raises(SSRFProtectionException):
        sec.validate_outbound_url("http://192.168.1.10/database")

    # Block AWS/GCP Cloud Metadata (169.254.169.254)
    with pytest.raises(SSRFProtectionException):
        sec.validate_outbound_url("http://169.254.169.254/latest/meta-data")

    # Allow valid allowlisted domain
    assert sec.validate_outbound_url(
        "https://api.openstreetmap.org/search",
        allowlist_domains=["api.openstreetmap.org"],
    ) is True


@pytest.mark.asyncio
async def test_05_secret_redaction_and_pii_minimization():
    sec = SecurityManager()

    data = {
        "api_key": "sk_live_1234567890abcdef",
        "nested": {
            "client_secret": "super_secret_token_123",
            "normal_field": "visible_data",
        },
        "phone": "+919876543210",
        "latitude": 15.12345678,
        "longitude": 73.98765432,
        "blood_group": "O+",
    }

    # Redact secrets
    redacted = sec.redact_secrets(data)
    assert "sk_l****cdef" in redacted["api_key"]
    assert "supe****_123" in redacted["nested"]["client_secret"]
    assert redacted["nested"]["normal_field"] == "visible_data"

    # Minimize PII for non-emergency external dispatch
    minimized = sec.minimize_pii(redacted, is_emergency=False)
    assert minimized["latitude"] == 15.123  # Rounded to 3 decimals
    assert minimized["longitude"] == 73.988
    assert "blood_group" not in minimized


@pytest.mark.asyncio
async def test_06_dead_letter_queue_and_manual_retry():
    dlq = DeadLetterQueueService()
    rec = await dlq.enqueue(
        operation_name="dispatch_sms_twilio",
        integration_id="int_sms",
        provider_name="DEV_SMS_ADAPTER",
        integration_type=IntegrationType.SMS,
        idempotency_key="sms_tx_99",
        correlation_id="corr_dlq_01",
        attempt_count=3,
        max_attempts=3,
        error_code="RATE_LIMIT_EXCEEDED",
        error_message="HTTP 429 Too Many Requests",
        payload_summary={"phone": "+919876543210"},
    )
    assert rec.resolved is False

    # List unresolved
    unresolved = await dlq.list_records(resolved=False)
    assert any(r["record_id"] == rec.record_id for r in unresolved)

    # Authorized resolution
    ok = await dlq.mark_resolved(rec.record_id, actor_id="ADMIN_SARAH")
    assert ok is True

    record = await dlq.get_record(rec.record_id)
    assert record["resolved"] is True
    assert record["resolved_by"] == "ADMIN_SARAH"


@pytest.mark.asyncio
async def test_07_state_conflict_detection_and_resolution():
    conflict_svc = ExternalConflictService()

    # Conflicting state: TourSafe says RESOLVED, CAD says ON_SCENE
    conflict = await conflict_svc.detect_or_record_conflict(
        toursafe_incident_id="INC-2026-555",
        external_system="DEV_EMERGENCY_CAD",
        external_incident_id="CAD-8888",
        toursafe_status="RESOLVED",
        external_status="ON_SCENE",
    )
    assert conflict is not None
    assert conflict.toursafe_status == "RESOLVED"
    assert conflict.external_status == "ON_SCENE"

    # Resolve conflict with policy
    resolved = await conflict_svc.resolve_conflict(
        conflict_id=conflict.conflict_id,
        policy="TOURSAFE_WINS",
        chosen_status="RESOLVED",
        actor_id="COMMANDER_VIKRAM",
    )
    assert resolved.resolved is True
    assert resolved.resolution_policy == "TOURSAFE_WINS"
    assert resolved.resolved_status == "RESOLVED"
