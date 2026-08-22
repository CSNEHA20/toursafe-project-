"""
Unit and Integration Tests for Disaster Recovery, Backups, Restores, Dead-Letter Queues, and Chaos Drills.
"""

import os
import pytest
from app.services.reliability.backup_service import backup_service
from app.services.reliability.restore_service import restore_service
from app.services.reliability.chaos_engine import chaos_engine
from app.core.reliability.queue_resilience import dead_letter_manager
from app.core.reliability.db_resilience import idempotent_write_guard, slow_query_tracker
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
        self.users = MockCollection("users")
        self.geospatial_zones = MockCollection("geospatial_zones")
        self.dead_letter_queue = MockCollection("dead_letter_queue")
        self.system_backups = MockCollection("system_backups")

    def __getitem__(self, name):
        if not hasattr(self, name):
            setattr(self, name, MockCollection(name))
        return getattr(self, name)

    async def command(self, cmd, **kwargs):
        return {"ok": 1}


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    mock_db = MockDB()
    monkeypatch.setattr(db_module, "get_database", lambda: mock_db)
    return mock_db


@pytest.mark.asyncio
async def test_01_snapshot_backup_creation_and_integrity_check():
    db = db_module.get_database()
    # Seed a test incident to ensure data exists
    await db.incidents.insert_one({
        "incident_id": "INC-BKP-TEST-001",
        "type": "SOS_PANIC",
        "severity": "CRITICAL",
        "timestamp": "2026-08-22T12:00:00Z",
    })

    # Create backup snapshot
    backup_meta = await backup_service.create_backup(collections=["incidents", "geospatial_zones"], actor_id="test_runner")
    assert backup_meta["status"] == "COMPLETED"
    assert backup_meta["total_documents"] >= 1
    assert os.path.exists(backup_meta["file_path"])
    assert backup_meta["checksum_sha256"] is not None

    # Verify backup archive checksum integrity
    integrity = await backup_service.verify_backup_integrity(backup_meta["backup_id"])
    assert integrity["valid"] is True
    assert integrity["calculated_checksum"] == backup_meta["checksum_sha256"]


@pytest.mark.asyncio
async def test_02_database_restoration_dry_run_and_actual():
    db = db_module.get_database()
    await db.incidents.insert_one({
        "incident_id": "INC-RESTORE-001",
        "type": "SOS_PANIC",
        "severity": "HIGH",
        "timestamp": "2026-08-22T12:00:00Z",
    })

    # 1. Create a known backup
    backup_meta = await backup_service.create_backup(collections=["incidents"], actor_id="test_runner")

    # 2. Dry run restore
    dry_run_result = await restore_service.restore_from_backup(
        backup_id=backup_meta["backup_id"],
        dry_run=True,
        actor_id="test_runner"
    )
    assert dry_run_result["success"] is True
    assert dry_run_result["dry_run"] is True
    assert dry_run_result["rto_seconds"] >= 0

    # 3. Actual restore
    actual_restore = await restore_service.restore_from_backup(
        backup_id=backup_meta["backup_id"],
        dry_run=False,
        actor_id="test_runner"
    )
    assert actual_restore["success"] is True
    assert actual_restore["dry_run"] is False

    # 4. Consistency verification
    consistency = await restore_service.verify_system_consistency()
    assert consistency["healthy"] is True


@pytest.mark.asyncio
async def test_03_dead_letter_queue_capture_and_replay():
    payload = {"tourist_id": "T-999", "channel": "SMS", "message": "Emergency broadcast alert"}
    error = TimeoutError("SMS Gateway Connection Timed Out")

    # 1. Capture to DLQ
    job_id = await dead_letter_manager.record_dead_letter(
        queue_name="notifications_queue",
        payload=payload,
        error=error,
        attempts=3,
    )
    assert job_id.startswith("dlq-")

    # 2. Inspect DLQ
    dlq_items = await dead_letter_manager.list_dead_letters(queue_name="notifications_queue")
    found = any(item["job_id"] == job_id for item in dlq_items)
    assert found is True

    # 3. Replay DLQ message
    replayed_payload = None

    async def mock_replay_handler(p):
        nonlocal replayed_payload
        replayed_payload = p

    replay_res = await dead_letter_manager.replay_message(
        job_id=job_id,
        handler=mock_replay_handler,
        actor_id="admin_test"
    )
    assert replay_res["success"] is True
    assert replayed_payload == payload


def test_04_idempotency_guard_and_slow_query_tracker():
    # Idempotency deduplication
    key = "sos_device_456_seq_10"
    assert idempotent_write_guard.is_duplicate(key) is False
    assert idempotent_write_guard.is_duplicate(key) is True

    # Slow query tracker
    slow_query_tracker.record("find", "incidents", 125.5, {"status": "OPEN"})
    slow_list = slow_query_tracker.get_slow_queries()
    assert len(slow_list) >= 1
    assert slow_list[0]["duration_ms"] == 125.5


@pytest.mark.asyncio
async def test_05_chaos_resilience_drills_suite():
    # Run full chaos suite
    suite_report = await chaos_engine.run_full_resilience_suite()
    assert suite_report["all_passed"] is True
    assert suite_report["total_drills"] == 5
    
    scenario_names = [d["scenario"] for d in suite_report["drills"]]
    assert "db_transient_timeout_recovery" in scenario_names
    assert "redis_outage_fallback_cache" in scenario_names
    assert "out_of_order_event_rejection" in scenario_names
    assert "duplicate_sos_flood_idempotency" in scenario_names
    assert "degradation_load_shedding" in scenario_names
