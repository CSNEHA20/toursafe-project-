import asyncio
import copy
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import settings
import app.core.database as db_module
import app.routers.auth as auth_router_mod
import app.routers.telemetry as telemetry_router_mod
import app.services.telemetry.session as telemetry_session_mod
import app.services.telemetry.persistence as telemetry_persistence_mod
from app.core.security import create_access_token
from app.main import app
from app.schemas.telemetry import (
    AccelerometerChannels,
    GPSPayload,
    GyroscopeChannels,
    QualityStateEnum,
    SessionStatusEnum,
    TelemetryAckStatus,
    TelemetryBatchRequest,
    TelemetryPacketEnvelope,
    TelemetryPacketType,
    TelemetrySample,
)
from app.services.telemetry import (
    quality_evaluator,
    telemetry_persistence,
    telemetry_queue,
    telemetry_redis_state,
    telemetry_service,
    telemetry_session_manager,
    telemetry_validator,
    telemetry_window_engine,
    TelemetryValidationException,
)
from app.services.telemetry.windowing import SessionWindowBuffer


class MockMongoCollection:
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
                if "$gte" in v and "$lte" in v:
                    if not (v["$gte"] <= str(val) <= v["$lte"]):
                        return False
                elif "$gte" in v:
                    if not (str(val) >= v["$gte"]):
                        return False
                elif "$lte" in v:
                    if not (str(val) <= v["$lte"]):
                        return False
                elif "$lt" in v:
                    if not (str(val) < v["$lt"]):
                        return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    async def find_one(self, filter_dict=None, sort=None, *args, **kwargs):
        docs_copy = list(self.docs)
        if sort:
            for sort_key, sort_dir in sort:
                docs_copy.sort(key=lambda x: str(x.get(sort_key, "")), reverse=(sort_dir == -1))
        if not filter_dict:
            return copy.deepcopy(docs_copy[0]) if docs_copy else None
        for doc in docs_copy:
            if self._matches(doc, filter_dict):
                return copy.deepcopy(doc)
        return None

    def find(self, filter_dict=None, *args, **kwargs):
        filtered = []
        filter_dict = filter_dict or {}
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                filtered.append(copy.deepcopy(doc))

        class Cursor:
            def __init__(self, items):
                self.items = items
                self._skip = 0
                self._limit = len(items)

            def sort(self, key, direction=1):
                reverse = direction == -1
                self.items.sort(key=lambda x: str(x.get(key, "")), reverse=reverse)
                return self

            def skip(self, n):
                self._skip = n
                return self

            def limit(self, n):
                self._limit = n
                return self

            async def to_list(self, length=None):
                limit_val = self._limit if length is None else length
                return self.items[self._skip : self._skip + limit_val]

            def __aiter__(self):
                self._iter_idx = self._skip
                self._iter_end = min(self._skip + self._limit, len(self.items))
                return self

            async def __anext__(self):
                if self._iter_idx >= self._iter_end:
                    raise StopAsyncIteration
                item = self.items[self._iter_idx]
                self._iter_idx += 1
                return item

        return Cursor(filtered)

    async def insert_one(self, document):
        doc = copy.deepcopy(document)
        if "id" not in doc:
            doc["id"] = f"id_{len(self.docs) + 1}"
        if "_id" not in doc:
            doc["_id"] = doc["id"]
        self.docs.append(doc)
        return type("Obj", (), {"inserted_id": doc["id"]})()

    async def insert_many(self, documents, ordered=False):
        inserted = []
        for d in documents:
            doc = copy.deepcopy(d)
            if "id" not in doc:
                doc["id"] = f"id_{len(self.docs) + 1}"
            self.docs.append(doc)
            inserted.append(doc["id"])
        return type("Obj", (), {"inserted_ids": inserted})()

    async def update_one(self, filter_dict, update_dict, upsert=False, *args, **kwargs):
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                if "$set" in update_dict:
                    doc.update(copy.deepcopy(update_dict["$set"]))
                return type("Obj", (), {"modified_count": 1, "matched_count": 1})()
        if upsert:
            new_doc = copy.deepcopy(filter_dict)
            if "$setOnInsert" in update_dict:
                new_doc.update(copy.deepcopy(update_dict["$setOnInsert"]))
            if "$set" in update_dict:
                new_doc.update(copy.deepcopy(update_dict["$set"]))
            self.docs.append(new_doc)
            return type("Obj", (), {"modified_count": 0, "matched_count": 0, "upserted_id": new_doc.get("id", "new")})()
        return type("Obj", (), {"modified_count": 0, "matched_count": 0})()

    async def find_one_and_update(self, filter_dict, update_dict, *args, **kwargs):
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                if "$set" in update_dict:
                    doc.update(copy.deepcopy(update_dict["$set"]))
                return copy.deepcopy(doc)
        return None

    async def delete_many(self, filter_dict=None):
        filter_dict = filter_dict or {}
        before = len(self.docs)
        self.docs = [d for d in self.docs if not self._matches(d, filter_dict)]
        deleted = before - len(self.docs)
        return type("Obj", (), {"deleted_count": deleted})()

    async def count_documents(self, filter_dict=None):
        filter_dict = filter_dict or {}
        return sum(1 for doc in self.docs if self._matches(doc, filter_dict))

    async def create_index(self, *args, **kwargs):
        return "index_created"


class MockAppDatabase:
    def __init__(self):
        self.tourists = MockMongoCollection("tourists")
        self.tourist_profiles = MockMongoCollection("tourist_profiles")
        self.users = MockMongoCollection("users")
        self.telemetry_samples = MockMongoCollection("telemetry_samples")
        self.telemetry_windows = MockMongoCollection("telemetry_windows")
        self.telemetry_sessions = MockMongoCollection("telemetry_sessions")

    def __getitem__(self, name):
        if not hasattr(self, name):
            setattr(self, name, MockMongoCollection(name))
        return getattr(self, name)

    async def command(self, *args, **kwargs):
        return {"ok": 1}


@pytest.fixture(autouse=True)
def mock_db_fixture(monkeypatch):
    mock_db = MockAppDatabase()
    # Seed mock tourist user
    mock_db.users.docs.append({
        "id": "usr_tourist_test_1",
        "email": "tourist1@example.com",
        "role": "tourist",
        "is_active": True,
    })
    mock_db.tourists.docs.append({
        "id": "tourist_test_1",
        "user_id": "usr_tourist_test_1",
        "full_name": "Test Tourist",
        "email": "tourist1@example.com",
    })
    # Seed authority user
    mock_db.users.docs.append({
        "id": "usr_auth_test_1",
        "email": "officer1@example.com",
        "role": "authority",
        "is_active": True,
    })

    monkeypatch.setattr(db_module, "get_database", lambda: mock_db)
    monkeypatch.setattr(auth_router_mod, "get_database", lambda: mock_db)

    from unittest.mock import AsyncMock
    import app.core.redis as redis_mod
    monkeypatch.setattr(redis_mod, "get_redis_client", AsyncMock(return_value=None))
    monkeypatch.setattr(redis_mod, "check_redis_health", AsyncMock(return_value={"status": "degraded", "connected": False}))
    return mock_db


@pytest.fixture
def auth_headers():
    token = create_access_token("usr_tourist_test_1", "tourist")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def authority_headers():
    token = create_access_token("usr_auth_test_1", "authority")
    return {"Authorization": f"Bearer {token}"}
 
@pytest.fixture(autouse=True)
def cleanup_queue():
    yield
    telemetry_queue.shutdown_sync()


# ─── 1. Packet Model & Validation Unit Tests ──────────────────────────────────

class TestTelemetryValidation:
    def test_valid_timestamp(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        dt, latency_ms = telemetry_validator.validate_timestamp(now_iso)
        assert isinstance(dt, datetime)
        assert latency_ms >= 0.0

    def test_future_timestamp_rejected(self):
        future_iso = (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat()
        with pytest.raises(TelemetryValidationException) as exc:
            telemetry_validator.validate_timestamp(future_iso)
        assert "future" in exc.value.message

    def test_expired_timestamp_rejected(self):
        old_iso = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        with pytest.raises(TelemetryValidationException) as exc:
            telemetry_validator.validate_timestamp(old_iso)
        assert "older than 24 hours" in exc.value.message

    def test_normalize_gps_envelope(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        envelope = TelemetryPacketEnvelope(
            packet_type=TelemetryPacketType.GPS_SAMPLE,
            session_id="sess_unit_1",
            sequence_number=1,
            timestamp=now_iso,
            payload={
                "latitude": 12.9716,
                "longitude": 77.5946,
                "altitude": 920.5,
                "accuracy": 4.5,
                "speed": 1.2,
                "heading": 180.0,
            },
        )
        sample = telemetry_validator.normalize_envelope(
            envelope=envelope,
            authenticated_tourist_id="tourist_123",
            user_id="user_123",
        )
        assert sample.tourist_id == "tourist_123"
        assert sample.gps is not None
        assert sample.gps.latitude == 12.9716
        assert sample.gps.longitude == 77.5946

    def test_normalize_imu_envelope_and_derive_kinematics(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        envelope = TelemetryPacketEnvelope(
            packet_type=TelemetryPacketType.IMU_SAMPLE,
            session_id="sess_unit_2",
            sequence_number=2,
            timestamp=now_iso,
            payload={
                "accelerometer": {"x": 0.0, "y": 0.0, "z": 1.0},
                "gyroscope": {"x": 0.0, "y": 0.0, "z": 0.0},
            },
        )
        sample = telemetry_validator.normalize_envelope(
            envelope=envelope,
            authenticated_tourist_id="tourist_123",
            user_id="user_123",
        )
        assert sample.accelerometer is not None
        assert sample.gyroscope is not None
        assert sample.derived is not None
        assert math.isclose(sample.derived.acceleration_magnitude, 1.0, abs_tol=1e-3)
        assert math.isclose(sample.derived.angular_velocity_magnitude, 0.0, abs_tol=1e-3)


# ─── 2. Sequence Management & Idempotency Tests ───────────────────────────────

class TestSequenceManagement:
    @pytest.mark.asyncio
    async def test_monotonic_sequence_flow(self):
        session = await telemetry_session_manager.get_or_create_session(
            session_id="sess_seq_test_1",
            tourist_id="tourist_seq_1",
            user_id="user_seq_1",
        )
        now = datetime.now(timezone.utc)

        # 1. First packet
        st1 = session.process_sequence("pkt_1", 1, now)
        assert st1 == TelemetryAckStatus.ACCEPTED
        assert session.highest_contiguous_sequence == 1

        # 2. Duplicate packet (idempotent)
        st_dup = session.process_sequence("pkt_1", 1, now)
        assert st_dup == TelemetryAckStatus.DUPLICATE
        assert session.duplicate_packets == 1

        # 3. Sequence jump (gap)
        st3 = session.process_sequence("pkt_3", 3, now)
        assert st3 == TelemetryAckStatus.ACCEPTED
        assert session.highest_sequence == 3
        assert session.highest_contiguous_sequence == 1
        assert session.estimated_missing_packets == 1

        # 4. Out-of-order fill of missing sequence
        st2 = session.process_sequence("pkt_2", 2, now)
        assert st2 == TelemetryAckStatus.OUT_OF_ORDER
        assert session.highest_contiguous_sequence == 3


# ─── 3. Window Engine Tests ───────────────────────────────────────────────────

class TestTelemetryWindowEngine:
    def test_3_second_window_generation(self):
        start_time = datetime.now(timezone.utc)
        buf = SessionWindowBuffer("sess_win_1", "tourist_win_1")

        # Generate 160 samples over 3.2 seconds (50 Hz)
        for i in range(160):
            t = start_time + timedelta(milliseconds=i * 20)  # 20ms = 50 Hz
            sample = TelemetrySample(
                session_id="sess_win_1",
                tourist_id="tourist_win_1",
                sequence_number=i + 1,
                timestamp=t.isoformat(),
                accelerometer=AccelerometerChannels(x=0.0, y=0.0, z=1.0),
                gyroscope=GyroscopeChannels(x=0.0, y=0.0, z=0.0),
                gps=GPSPayload(latitude=12.97, longitude=77.59, accuracy=5.0) if i == 0 else None,
            )
            buf.add_sample(sample)

        windows = telemetry_window_engine.process_buffer(
            buf=buf,
            duration_sec=3.0,
            stride_sec=1.0,
            target_hz=50.0,
            min_completeness=0.6,
            max_gap_ms=250.0,
        )

        assert len(windows) >= 1
        w0 = windows[0]
        assert w0.duration_seconds == 3.0
        assert w0.is_valid is True
        assert w0.completeness_ratio >= 0.8
        assert w0.sample_count >= 140
        assert w0.gps_context is not None

    def test_invalid_window_with_large_gap(self):
        start_time = datetime.now(timezone.utc)
        buf = SessionWindowBuffer("sess_win_gap", "tourist_win_gap")

        # Sample 1..50
        for i in range(50):
            t = start_time + timedelta(milliseconds=i * 20)
            buf.add_sample(
                TelemetrySample(
                    session_id="sess_win_gap",
                    tourist_id="tourist_win_gap",
                    sequence_number=i + 1,
                    timestamp=t.isoformat(),
                    accelerometer=AccelerometerChannels(x=0.0, y=0.0, z=1.0),
                    gyroscope=GyroscopeChannels(x=0.0, y=0.0, z=0.0),
                )
            )

        # 600ms gap (> 250ms tolerance)
        jump_time = start_time + timedelta(milliseconds=1000 + 600)
        for i in range(50, 100):
            t = jump_time + timedelta(milliseconds=(i - 50) * 20)
            buf.add_sample(
                TelemetrySample(
                    session_id="sess_win_gap",
                    tourist_id="tourist_win_gap",
                    sequence_number=i + 1,
                    timestamp=t.isoformat(),
                    accelerometer=AccelerometerChannels(x=0.0, y=0.0, z=1.0),
                    gyroscope=GyroscopeChannels(x=0.0, y=0.0, z=0.0),
                )
            )

        windows = telemetry_window_engine.process_buffer(
            buf=buf,
            duration_sec=3.0,
            stride_sec=1.0,
            target_hz=50.0,
            min_completeness=0.5,
            max_gap_ms=250.0,
        )

        if windows:
            assert windows[0].is_valid is False
            assert any("gap" in err.lower() for err in windows[0].validation_errors)


# ─── 4. End-to-End API Integration Tests ──────────────────────────────────────

class TestTelemetryAPIEndpoints:
    def test_session_lifecycle(self, auth_headers):
        from fastapi.testclient import TestClient
        client = TestClient(app)

        # 1. Start session
        res_start = client.post(
            "/api/v1/telemetry/session/start",
            headers=auth_headers,
            json={"device_id": "test_device_42", "sampling_rate_target_hz": 50.0},
        )
        assert res_start.status_code == 200
        data_start = res_start.json()
        session_id = data_start["session_id"]
        assert data_start["status"] == "active"

        # 2. Ingest valid combined packet
        now_iso = datetime.now(timezone.utc).isoformat()
        packet_body = {
            "packet_id": f"pkt_test_{int(time.time())}",
            "packet_type": "telemetry.sample",
            "session_id": session_id,
            "sequence_number": 1,
            "timestamp": now_iso,
            "payload": {
                "latitude": 12.9716,
                "longitude": 77.5946,
                "accuracy": 6.2,
                "accelerometer": {"x": 0.05, "y": -0.02, "z": 0.98},
                "gyroscope": {"x": 0.01, "y": 0.02, "z": -0.01},
            },
        }

        res_ingest = client.post(
            "/api/v1/telemetry/packet",
            headers=auth_headers,
            json=packet_body,
        )
        assert res_ingest.status_code == 200
        ack = res_ingest.json()
        assert ack["status"] == "accepted"
        assert ack["sequence_number"] == 1
        assert ack["highest_contiguous_sequence"] == 1

        # 3. Duplicate packet ingestion (idempotent test)
        res_dup = client.post(
            "/api/v1/telemetry/packet",
            headers=auth_headers,
            json=packet_body,
        )
        assert res_dup.status_code == 200
        assert res_dup.json()["status"] == "duplicate"

        # 4. Ingest bounded batch
        batch_packets = []
        for seq in range(2, 6):
            t_iso = (datetime.now(timezone.utc) + timedelta(milliseconds=(seq - 1) * 20)).isoformat()
            batch_packets.append({
                "packet_id": f"pkt_batch_{seq}_{int(time.time())}",
                "packet_type": "imu.sample",
                "session_id": session_id,
                "sequence_number": seq,
                "timestamp": t_iso,
                "payload": {
                    "accelerometer": {"x": 0.01, "y": 0.0, "z": 0.99},
                    "gyroscope": {"x": 0.0, "y": 0.0, "z": 0.0},
                },
            })

        res_batch = client.post(
            "/api/v1/telemetry/batch",
            headers=auth_headers,
            json={"session_id": session_id, "packets": batch_packets},
        )
        assert res_batch.status_code == 200
        batch_ack = res_batch.json()
        assert batch_ack["accepted_count"] == 4
        assert batch_ack["highest_contiguous_sequence"] == 5

        # 5. Check tourist telemetry status
        res_status = client.get(
            "/api/v1/tourists/me/telemetry/status",
            headers=auth_headers,
        )
        assert res_status.status_code == 200
        status_data = res_status.json()
        assert status_data["active_session_id"] == session_id
        assert status_data["tracking_status"] == "active"

        # 6. Stop session
        res_stop = client.post(
            "/api/v1/telemetry/session/stop",
            headers=auth_headers,
            json={"session_id": session_id},
        )
        assert res_stop.status_code == 200
        assert res_stop.json()["status"] == "stopped"

    def test_authority_operational_view_privacy(self, authority_headers, auth_headers):
        """Verify that Authority endpoint receives summarized metrics without raw 50 Hz IMU streams."""
        from fastapi.testclient import TestClient
        client = TestClient(app)

        res_auth = client.get(
            "/api/v1/authority/tourists/tourist_test_1/telemetry-status",
            headers=authority_headers,
        )
        assert res_auth.status_code == 200
        auth_view = res_auth.json()
        assert "tourist_id" in auth_view
        assert "overall_quality" in auth_view
        assert "accelerometer" not in auth_view
        assert "gyroscope" not in auth_view

        res_diag = client.get(
            "/api/v1/authority/telemetry-diagnostics",
            headers=authority_headers,
        )
        assert res_diag.status_code == 200
        diag = res_diag.json()
        assert "queue_depth" in diag
        assert "queue_capacity" in diag
        assert "processing_latency_ms" in diag


# ─── 5. Synthetic Load & Backpressure Test ────────────────────────────────────

class TestTelemetryLoadAndBackpressure:
    def test_simulated_50hz_telemetry_streaming(self, auth_headers):
        """Simulate high-frequency 50 Hz ingestion over 1 session, then 5 concurrent sessions via batch."""
        from fastapi.testclient import TestClient
        client = TestClient(app)

        session_ids = [f"load_sess_{i}_{int(time.time())}" for i in range(5)]
        total_samples = 0
        start_time = time.perf_counter()

        for s_idx, sess_id in enumerate(session_ids):
            # Send batch of 50 samples = 1 full second of 50 Hz IMU
            batch_packets = []
            for seq in range(1, 51):
                t_iso = (datetime.now(timezone.utc) + timedelta(milliseconds=seq * 20)).isoformat()
                batch_packets.append({
                    "packet_id": f"pkt_load_{s_idx}_{seq}",
                    "packet_type": "imu.sample",
                    "session_id": sess_id,
                    "sequence_number": seq,
                    "timestamp": t_iso,
                    "payload": {
                        "accelerometer": {"x": 0.02, "y": 0.01, "z": 0.98},
                        "gyroscope": {"x": 0.005, "y": -0.002, "z": 0.001},
                    },
                })

            res = client.post(
                "/api/v1/telemetry/batch",
                headers=auth_headers,
                json={"session_id": sess_id, "packets": batch_packets},
            )
            assert res.status_code == 200
            ack = res.json()
            assert ack["accepted_count"] == 50
            total_samples += 50

        elapsed = time.perf_counter() - start_time
        throughput = round(total_samples / max(0.001, elapsed), 2)
        assert total_samples == 250
        assert throughput > 50.0  # High-throughput asynchronous pipeline
