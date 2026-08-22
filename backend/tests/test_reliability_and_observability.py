"""
Unit and Integration Tests for TourSafe Reliability, Observability & Tracing Infrastructure.
"""

import json
import logging
import pytest
from app.core.reliability.metrics import (
    metrics_collector,
    SlidingWindowLatency,
    GoldenSignals,
    SubsystemMetrics,
)
from app.core.reliability.tracing import (
    set_trace_context,
    get_current_trace_id,
    get_current_correlation_id,
    trace_context,
)
from app.core.reliability.logging import redact_sensitive_data, StructuredJsonFormatter
from app.services.reliability.incident_timeline import incident_timeline_service
import app.core.database as db_module


class MockCollection:
    def __init__(self, name="collection"):
        self.name = name
        self.docs = []

    async def insert_one(self, doc):
        d = doc.copy()
        if "_id" not in d:
            d["_id"] = f"mock_{len(self.docs)+1}"
        self.docs.append(d)
        return type("InsertResult", (), {"inserted_id": d["_id"]})()

    async def find_one(self, filter_dict=None):
        filter_dict = filter_dict or {}
        for d in self.docs:
            if self._matches(d, filter_dict):
                return d
        return None

    def find(self, filter_dict=None):
        filter_dict = filter_dict or {}
        matches = [d for d in self.docs if self._matches(d, filter_dict)]

        class AsyncCursor:
            def __init__(self, items):
                self.items = items

            def sort(self, key, direction=1):
                return self

            def limit(self, count):
                self.items = self.items[:count]
                return self

            async def to_list(self, length=100):
                return [d.copy() for d in self.items[:length]]

        return AsyncCursor(matches)

    async def count_documents(self, filter_dict=None):
        filter_dict = filter_dict or {}
        return sum(1 for d in self.docs if self._matches(d, filter_dict))

    async def replace_one(self, filter_dict, doc, upsert=False):
        for i, d in enumerate(self.docs):
            if self._matches(d, filter_dict):
                self.docs[i] = doc.copy()
                return type("ReplaceResult", (), {"matched_count": 1, "modified_count": 1})()
        if upsert:
            self.docs.append(doc.copy())
            return type("ReplaceResult", (), {"matched_count": 0, "upserted_id": "upserted_1"})()
        return type("ReplaceResult", (), {"matched_count": 0, "modified_count": 0})()

    def _matches(self, doc, filter_dict):
        for k, v in filter_dict.items():
            if doc.get(k) != v:
                return False
        return True


class MockDB:
    def __init__(self):
        self.incidents = MockCollection("incidents")
        self.emergency_dispatches = MockCollection("emergency_dispatches")
        self.notifications = MockCollection("notifications")
        self.audit_logs = MockCollection("audit_logs")
        self.dead_letter_queue = MockCollection("dead_letter_queue")
        self.system_backups = MockCollection("system_backups")

    def __getitem__(self, name):
        if not hasattr(self, name):
            setattr(self, name, MockCollection(name))
        return getattr(self, name)

    async def command(self, cmd, **kwargs):
        if cmd == "ping":
            return {"ok": 1}
        return {"ok": 1}


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    metrics_collector.reset_for_tests()
    mock_db = MockDB()
    monkeypatch.setattr(db_module, "get_database", lambda: mock_db)
    return mock_db


def test_01_sliding_window_latency_percentiles():
    tracker = SlidingWindowLatency(max_samples=100)
    for ms in [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]:
        tracker.record(ms)

    pct = tracker.get_percentiles()
    assert pct["count"] == 10
    assert pct["p50"] == 50.0
    assert pct["p95"] == 100.0
    assert pct["p99"] == 100.0
    assert pct["avg"] == 55.0


def test_02_golden_signals_metrics():
    golden = GoldenSignals()
    golden.record_request(status_code=200, duration_ms=25.0)
    golden.record_request(status_code=201, duration_ms=40.0)
    golden.record_request(status_code=400, duration_ms=10.0)
    golden.record_request(status_code=500, duration_ms=150.0)
    golden.record_dependency_error()

    summary = golden.get_summary()
    assert summary["traffic"]["total_requests"] == 4
    assert summary["traffic"]["requests_2xx"] == 2
    assert summary["traffic"]["requests_4xx"] == 1
    assert summary["traffic"]["requests_5xx"] == 1
    assert summary["errors"]["error_rate_5xx"] == 25.0
    assert summary["errors"]["dependency_errors"] == 1
    assert "cpu_percent" in summary["saturation"]
    assert "memory_rss_mb" in summary["saturation"]


def test_03_subsystem_telemetry_and_sos_metrics():
    sub = SubsystemMetrics()
    sub.record_sos(latency_ms=120.0, success=True)
    sub.record_sos(latency_ms=300.0, success=False)
    sub.record_telemetry(latency_ms=15.0, dropped=False, gap=False)
    sub.record_telemetry(latency_ms=0.0, dropped=True, gap=True)
    sub.record_db(latency_ms=150.0, is_error=False)  # slow query > 100ms
    sub.record_redis(latency_ms=5.0, is_error=False)
    sub.record_ai(latency_ms=800.0, is_timeout=False, is_fallback=True)

    summary = sub.get_summary()
    assert summary["incident_operations"]["sos_signals_received"] == 2
    assert summary["incident_operations"]["sos_processing_failures"] == 1
    assert summary["telemetry"]["packets_ingested"] == 1
    assert summary["telemetry"]["packets_dropped"] == 1
    assert summary["telemetry"]["sequence_gaps"] == 1
    assert summary["database"]["slow_queries"] == 1
    assert summary["ml_and_ai"]["ai_fallbacks"] == 1


def test_04_prometheus_export_format():
    metrics_collector.golden.record_request(200, 35.0)
    metrics_collector.subsystems.record_sos(100.0, True)
    metrics_collector.subsystems.record_telemetry(12.0, False, False)

    prom_text = metrics_collector.export_prometheus()
    assert "toursafe_uptime_seconds" in prom_text
    assert 'toursafe_http_requests_total{status="2xx"} 1' in prom_text
    assert "toursafe_sos_signals_total 1" in prom_text
    assert "toursafe_telemetry_packets_total 1" in prom_text


def test_05_distributed_tracing_and_correlation_propagation():
    set_trace_context(trace_id="trc-test-12345", correlation_id="cor-test-67890")
    assert get_current_trace_id() == "trc-test-12345"
    assert get_current_correlation_id() == "cor-test-67890"

    with trace_context("span_test_sub_op"):
        assert get_current_trace_id() == "trc-test-12345"


def test_06_sensitive_data_redaction_and_structured_logging():
    raw_payload = {
        "user_id": "usr-99",
        "password": "SuperSecretPassword123!",
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThis",
        "auth_header": "Bearer secret_bearer_token_xyz12345",
        "nested": {
            "api_key": "sk-1234567890abcdef",
            "passport_number": "P12345678",
            "safe_field": "public_tourist_name",
        },
    }

    redacted = redact_sensitive_data(raw_payload)
    assert redacted["password"] == "[REDACTED_SECRET]"
    assert redacted["token"] == "[REDACTED_SECRET]"
    assert "[REDACTED_TOKEN]" in redacted["auth_header"]
    assert redacted["nested"]["api_key"] == "[REDACTED_SECRET]"
    assert redacted["nested"]["passport_number"] == "[REDACTED_SECRET]"
    assert redacted["nested"]["safe_field"] == "public_tourist_name"

    formatter = StructuredJsonFormatter()
    record = logging.LogRecord("test_logger", logging.INFO, "test.py", 10, "Test log message", (), None)
    record.extra_data = raw_payload
    formatted_json = formatter.format(record)
    parsed = json.loads(formatted_json)
    assert parsed["service"] == "toursafe-backend"
    assert parsed["message"] == "Test log message"
    assert parsed["data"]["password"] == "[REDACTED_SECRET]"


@pytest.mark.asyncio
async def test_07_incident_unified_timeline_reconstruction():
    db = db_module.get_database()
    test_inc_id = "INC-TEST-TIMELINE-001"
    
    await db.incidents.replace_one(
        {"incident_id": test_inc_id},
        {
            "incident_id": test_inc_id,
            "type": "SOS_PANIC",
            "severity": "CRITICAL",
            "created_at": "2026-08-22T10:00:00Z",
            "status": "OPEN",
        },
        upsert=True
    )

    await db.emergency_dispatches.insert_one({
        "incident_id": test_inc_id,
        "responder_id": "RESP-101",
        "unit_type": "AMBULANCE",
        "dispatched_at": "2026-08-22T10:02:00Z",
    })

    await db.notifications.insert_one({
        "incident_id": test_inc_id,
        "recipient_role": "RESPONDER",
        "channel": "SMS",
        "status": "DELIVERED",
        "sent_at": "2026-08-22T10:02:30Z",
    })

    timeline = await incident_timeline_service.get_incident_timeline(test_inc_id)
    assert timeline["incident_id"] == test_inc_id
    assert timeline["total_events"] >= 3
    event_types = [e["event_type"] for e in timeline["timeline"]]
    assert "INCIDENT_CREATED" in event_types
    assert "RESPONDER_DISPATCHED" in event_types
    assert "NOTIFICATION_SENT" in event_types
