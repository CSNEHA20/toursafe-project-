import copy
import math
import pytest
import sys
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, "backend")

from app.main import app
import app.core.database as db_module
import app.routers.imu as imu_router_mod
from app.core.security import create_access_token
from app.schemas.imu import (
    AccelerometerChannels,
    GyroscopeChannels,
    IMUSampleIn,
    IMUSampleBatchIn,
)


class MockMongoCollection:
    def __init__(self, name: str):
        self.name = name
        self.docs = []

    def _matches(self, doc, filter_dict):
        for k, v in filter_dict.items():
            if k == "$or":
                return any(self._matches(doc, cond) for cond in v)
            if doc.get(k) != v:
                return False
        return True

    async def find_one(self, filter_dict=None, *args, **kwargs):
        docs_copy = list(self.docs)
        if not filter_dict:
            return copy.deepcopy(docs_copy[0]) if docs_copy else None
        for doc in docs_copy:
            if self._matches(doc, filter_dict):
                return copy.deepcopy(doc)
        return None


class MockAppDatabase:
    def __init__(self):
        self.tourists = MockMongoCollection("tourists")
        self.users = MockMongoCollection("users")

    def __getitem__(self, name):
        if not hasattr(self, name):
            setattr(self, name, MockMongoCollection(name))
        return getattr(self, name)


@pytest.fixture(autouse=True)
def mock_db_fixture(monkeypatch):
    mock_db = MockAppDatabase()
    mock_db.users.docs.append({
        "id": "tourist_user_1",
        "email": "tourist@toursafe.dev",
        "role": "tourist",
        "full_name": "Test Tourist",
        "is_active": True,
    })
    mock_db.tourists.docs.append({
        "id": "tourist_me",
        "user_id": "tourist_user_1",
        "full_name": "Test Tourist",
    })

    monkeypatch.setattr(db_module, "get_database", lambda: mock_db)
    monkeypatch.setattr(imu_router_mod, "get_database", lambda: mock_db)
    return mock_db


@pytest.fixture
def tourist_token():
    return create_access_token("tourist_user_1", "tourist")


@pytest.fixture
def authority_token():
    return create_access_token("auth_user_1", "authority")


@pytest.fixture
def valid_imu_sample_dict():
    return {
        "session_id": "test_imu_session_1",
        "sequence_number": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "monotonic_timestamp_ms": 1000.5,
        "device_id": "dev_test_device_1",
        "accelerometer": {
            "x": 0.02,
            "y": -0.05,
            "z": 0.98,
        },
        "gyroscope": {
            "x": 0.001,
            "y": 0.002,
            "z": -0.003,
        },
        "derived": {
            "acceleration_magnitude": 0.9815,
            "angular_velocity_magnitude": 0.0037,
        },
        "quality": {
            "sensor_timestamp_delta_ms": 1.5,
            "is_synchronized": True,
            "quality_state": "excellent",
        },
    }


# ─── 1. Schema Validation Tests ───────────────────────────────────────────────

class TestIMUSchemaValidation:
    def test_valid_imu_sample_creation(self, valid_imu_sample_dict):
        sample = IMUSampleIn(**valid_imu_sample_dict)
        assert sample.session_id == "test_imu_session_1"
        assert sample.sequence_number == 1
        assert sample.accelerometer.z == 0.98
        assert sample.gyroscope.x == 0.001

    def test_server_magnitude_recomputation(self, valid_imu_sample_dict):
        sample = IMUSampleIn(**valid_imu_sample_dict)
        derived = sample.calculate_server_magnitudes()

        expected_a_mag = math.sqrt(0.02**2 + (-0.05)**2 + 0.98**2)
        expected_g_mag = math.sqrt(0.001**2 + 0.002**2 + (-0.003)**2)

        assert abs(derived.acceleration_magnitude - expected_a_mag) < 1e-4
        assert abs(derived.angular_velocity_magnitude - expected_g_mag) < 1e-4

    def test_sequence_number_must_be_positive(self, valid_imu_sample_dict):
        valid_imu_sample_dict["sequence_number"] = 0
        with pytest.raises(ValueError, match="Sequence number must be >= 1"):
            IMUSampleIn(**valid_imu_sample_dict)

    def test_invalid_timestamp_rejected(self, valid_imu_sample_dict):
        valid_imu_sample_dict["timestamp"] = "not-a-timestamp"
        with pytest.raises(ValueError, match="Invalid ISO 8601 timestamp string"):
            IMUSampleIn(**valid_imu_sample_dict)

    def test_future_timestamp_rejected(self, valid_imu_sample_dict):
        far_future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        valid_imu_sample_dict["timestamp"] = far_future
        with pytest.raises(ValueError, match="Timestamp is too far in the future"):
            IMUSampleIn(**valid_imu_sample_dict)

    def test_nan_coordinates_rejected(self, valid_imu_sample_dict):
        valid_imu_sample_dict["accelerometer"]["x"] = float("nan")
        with pytest.raises(ValueError, match="finite numbers"):
            IMUSampleIn(**valid_imu_sample_dict)


# ─── 2. REST Endpoint Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
class TestIMURESTEndpoints:
    async def test_ingest_single_sample_success(self, tourist_token, valid_imu_sample_dict):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/telemetry/imu",
                json=valid_imu_sample_dict,
                headers={"Authorization": f"Bearer {tourist_token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "accepted"
            assert data["session_id"] == "test_imu_session_1"
            assert data["sequence_number"] == 1
            assert data["recomputed_acceleration_magnitude"] > 0.9

    async def test_ingest_sample_unauthenticated_rejected(self, valid_imu_sample_dict):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/telemetry/imu",
                json=valid_imu_sample_dict,
            )
            assert response.status_code == 401

    async def test_ingest_sample_authority_forbidden(self, authority_token, valid_imu_sample_dict):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/telemetry/imu",
                json=valid_imu_sample_dict,
                headers={"Authorization": f"Bearer {authority_token}"},
            )
            assert response.status_code == 403

    async def test_ingest_batch_success(self, tourist_token, valid_imu_sample_dict):
        sample1 = dict(valid_imu_sample_dict, sequence_number=1)
        sample2 = dict(valid_imu_sample_dict, sequence_number=2)

        batch_payload = {
            "session_id": "test_imu_session_1",
            "samples": [sample1, sample2],
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/telemetry/imu/batch",
                json=batch_payload,
                headers={"Authorization": f"Bearer {tourist_token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "accepted"
            assert data["accepted_count"] == 2
            assert data["last_sequence_number"] == 2

    async def test_ingest_empty_batch_rejected(self, tourist_token):
        batch_payload = {
            "session_id": "test_imu_session_1",
            "samples": [],
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/telemetry/imu/batch",
                json=batch_payload,
                headers={"Authorization": f"Bearer {tourist_token}"},
            )
            assert response.status_code == 400
