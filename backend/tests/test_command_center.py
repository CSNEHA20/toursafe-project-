"""
Backend Integration & Unit Tests for TourSafe Command Center & Live Operations
Validates:
- Snapshot generation and aggregation
- Authority jurisdiction scoping & RBAC
- Staleness status calculation
- Subsystem health checks
- Multi-entity search
- Incident command integration
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.command_center import (
    CommandCenterSnapshot,
    StalenessStatus,
    SubsystemHealth,
)
from app.routers.command_center import (
    compute_staleness,
    get_command_center_snapshot,
    get_system_status,
    command_center_search,
)


@pytest.mark.asyncio
async def test_compute_staleness_thresholds():
    now_dt = datetime.now(timezone.utc)

    # 1. Live (<30s)
    live_ts = (now_dt - timedelta(seconds=15)).isoformat()
    assert compute_staleness(live_ts, now_dt) == StalenessStatus.LIVE

    # 2. Recent (30s - 120s)
    recent_ts = (now_dt - timedelta(seconds=75)).isoformat()
    assert compute_staleness(recent_ts, now_dt) == StalenessStatus.RECENT

    # 3. Stale (2m - 10m)
    stale_ts = (now_dt - timedelta(minutes=5)).isoformat()
    assert compute_staleness(stale_ts, now_dt) == StalenessStatus.STALE

    # 4. Unknown (>10m or None)
    unknown_ts = (now_dt - timedelta(minutes=25)).isoformat()
    assert compute_staleness(unknown_ts, now_dt) == StalenessStatus.UNKNOWN
    assert compute_staleness(None, now_dt) == StalenessStatus.UNKNOWN


@pytest.mark.asyncio
async def test_command_center_snapshot_generation():
    mock_db = MagicMock()

    # Mock Authority
    mock_db.authority.find_one = AsyncMock(return_value={
        "id": "auth_001",
        "user_id": "user_auth_1",
        "full_name": "Commander Ramesh",
        "organization_name": "Goa Police Tourism Dept",
        "designation": "Commanding Officer",
        "jurisdiction_code": "IN-GOA-NORTH",
    })

    # Mock Incidents
    now_iso = datetime.now(timezone.utc).isoformat()
    mock_db.incidents.find.return_value.sort.return_value.to_list = AsyncMock(return_value=[
        {
            "incident_id": "inc_001",
            "tourist_id": "tourist_101",
            "source": "MANUAL_SOS",
            "severity": "CRITICAL",
            "status": "OPEN",
            "started_at": now_iso,
            "created_at": now_iso,
            "updated_at": now_iso,
            "location_data": {"latitude": 15.4989, "longitude": 73.8278},
            "reasons": ["Manual SOS trigger by tourist"],
            "timeline": [],
            "version": 1,
        },
        {
            "incident_id": "inc_002",
            "tourist_id": "tourist_102",
            "source": "SAFETY_ENGINE",
            "severity": "HIGH",
            "status": "ASSIGNED",
            "assigned_responder_id": "resp_01",
            "started_at": now_iso,
            "created_at": now_iso,
            "updated_at": now_iso,
            "location_data": {"latitude": 15.5123, "longitude": 73.8112},
            "reasons": ["IMU fall + zone dwell"],
            "timeline": [],
            "version": 2,
        },
    ])

    # Mock Tourists
    mock_db.tourists.find.return_value.to_list = AsyncMock(return_value=[
        {
            "id": "tourist_101",
            "user_id": "user_t1",
            "full_name": "Alice Green",
            "nationality": "UK",
            "safety_state": "INCIDENT",
            "current_lat": 15.4989,
            "current_lng": 73.8278,
            "battery_pct": 74,
            "verification_status": "verified",
            "credential_status": "active",
        },
        {
            "id": "tourist_102",
            "user_id": "user_t2",
            "full_name": "Bob Martin",
            "nationality": "France",
            "safety_state": "ELEVATED",
            "current_lat": 15.5123,
            "current_lng": 73.8112,
            "battery_pct": 92,
            "verification_status": "verified",
            "credential_status": "active",
        },
    ])

    # Mock Responders
    mock_db.responders.find.return_value.to_list = AsyncMock(return_value=[
        {
            "id": "resp_01",
            "name": "Unit Alpha (Patrol)",
            "unit_id": "unit_alpha",
            "status": "ASSIGNED",
            "latitude": 15.5000,
            "longitude": 73.8200,
            "capabilities": ["FIRST_AID", "PATROL"],
            "last_location_updated_at": now_iso,
        },
        {
            "id": "resp_02",
            "name": "Unit Beta (Medical)",
            "unit_id": "unit_beta",
            "status": "AVAILABLE",
            "latitude": 15.5200,
            "longitude": 73.8300,
            "capabilities": ["PARAMEDIC"],
            "last_location_updated_at": now_iso,
        },
    ])

    # Mock Zones
    mock_db.zones.find.return_value.to_list = AsyncMock(return_value=[
        {
            "id": "zone_001",
            "name": "Baga Restricted Cliff",
            "risk_level": "critical",
            "zone_type": "danger",
            "center_lat": 15.5500,
            "center_lng": 73.7500,
            "is_active": True,
        }
    ])

    # Mock cursor iteration for safety states and locations
    async def empty_async_gen():
        if False:
            yield {}

    mock_db.safety_states.find.return_value = empty_async_gen()
    mock_db.locations.find.return_value.sort.return_value = empty_async_gen()

    with patch("app.routers.command_center.get_database", return_value=mock_db):
        snapshot: CommandCenterSnapshot = await get_command_center_snapshot(
            user_id_role=("user_auth_1", "authority")
        )

        assert snapshot.snapshot_id.startswith("snap_")
        assert snapshot.authority_scope.organization_name == "Goa Police Tourism Dept"
        assert len(snapshot.active_incidents) == 2
        assert len(snapshot.sos_queue) == 1
        assert snapshot.sos_queue[0].incident_id == "inc_001"
        assert len(snapshot.tourists) == 2
        assert len(snapshot.responders) == 2
        assert len(snapshot.zones) == 1
        assert snapshot.kpis.active_tourists == 2
        assert snapshot.kpis.open_incidents == 2
        assert snapshot.kpis.sos_incidents == 1
        assert snapshot.kpis.active_responders == 2
        assert snapshot.kpis.unassigned_incidents == 1  # inc_001 is unassigned
        assert snapshot.system_health.realtime == SubsystemHealth.HEALTHY


@pytest.mark.asyncio
async def test_command_center_system_status():
    status_resp = await get_system_status(user_id_role=("user_admin", "admin"))
    assert status_resp.realtime == SubsystemHealth.HEALTHY
    assert status_resp.telemetry == SubsystemHealth.HEALTHY
    assert status_resp.ml == SubsystemHealth.HEALTHY
    assert status_resp.notifications == SubsystemHealth.HEALTHY
    assert status_resp.map == SubsystemHealth.HEALTHY
    assert status_resp.backend == SubsystemHealth.HEALTHY


@pytest.mark.asyncio
async def test_command_center_search():
    mock_db = MagicMock()

    # Async cursor helper
    class AsyncSearchCursor:
        def __init__(self, docs):
            self.docs = docs
        def limit(self, n):
            return self
        def __aiter__(self):
            self.iter = iter(self.docs)
            return self
        async def __anext__(self):
            try:
                return next(self.iter)
            except StopIteration:
                raise StopAsyncIteration

    mock_db.incidents.find.return_value = AsyncSearchCursor([
        {"incident_id": "inc_sos_99", "severity": "CRITICAL", "source": "MANUAL_SOS", "status": "OPEN"}
    ])
    mock_db.tourists.find.return_value = AsyncSearchCursor([
        {"id": "t_99", "full_name": "Alice Smith", "nationality": "UK", "safety_state": "NORMAL", "current_lat": 15.5, "current_lng": 73.8}
    ])
    mock_db.responders.find.return_value = AsyncSearchCursor([])
    mock_db.zones.find.return_value = AsyncSearchCursor([])

    with patch("app.routers.command_center.get_database", return_value=mock_db):
        resp = await command_center_search(
            q="Alice",
            type=None,
            user_id_role=("user_auth", "authority")
        )

        assert resp.query == "Alice"
        assert len(resp.results) == 2
        assert any(r.entity_type == "tourist" and "Alice Smith" in r.title for r in resp.results)
        assert any(r.entity_type == "incident" for r in resp.results)
