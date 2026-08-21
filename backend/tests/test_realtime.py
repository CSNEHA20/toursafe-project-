import asyncio
import json
import pytest
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, "backend")

from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.core.connection_manager import ConnectionManager, ConnectionContext
from app.core.realtime_auth import can_subscribe_to_channel, get_default_channels
from app.schemas.realtime import (
    RealtimeEventEnvelope,
    RealtimeEventType,
    ALL_REGISTERED_EVENT_TYPES,
)
from app.services.realtime_bus import RealtimeEventBus


class TestRealtimeEventEnvelope:
    def test_valid_envelope_creation(self):
        env = RealtimeEventEnvelope(
            event_type="zone.updated",
            payload={"zone_id": "zone_123", "risk_level": "high"},
        )
        assert env.event_id.startswith("evt_")
        assert env.event_type == "zone.updated"
        assert env.version == 1
        assert env.source == "backend"
        assert env.payload["zone_id"] == "zone_123"
        assert env.timestamp is not None

    def test_invalid_event_type_rejected(self):
        with pytest.raises(ValueError):
            RealtimeEventEnvelope(
                event_type="invalidformat",
                payload={},
            )

    def test_version_validation(self):
        with pytest.raises(ValueError):
            RealtimeEventEnvelope(
                event_type="system.status",
                version=0,
                payload={},
            )

    def test_all_contract_event_types_registered(self):
        expected_types = [
            "system.connected", "system.disconnected", "system.status", "system.heartbeat",
            "tourist.profile.updated", "tourist.status.updated",
            "location.updated", "location.stale",
            "zone.created", "zone.updated", "zone.status_changed",
            "alert.created", "alert.updated", "alert.resolved",
            "sos.created", "sos.updated", "sos.resolved",
            "telemetry.started", "telemetry.stopped", "telemetry.status",
            "anomaly.detected", "anomaly.confirmed", "anomaly.cleared",
            "emergency.created", "emergency.updated", "emergency.dispatched",
            "identity.verified", "identity.access_granted", "identity.access_revoked",
            "efir.created", "efir.updated", "efir.dispatched",
        ]
        for event_name in expected_types:
            assert event_name in ALL_REGISTERED_EVENT_TYPES


class TestRealtimeChannelAuthorization:
    def test_tourist_own_user_channel_allowed(self):
        assert can_subscribe_to_channel("user_1", "tourist", "user:user_1") is True

    def test_tourist_other_user_channel_denied(self):
        assert can_subscribe_to_channel("user_1", "tourist", "user:user_2") is False

    def test_tourist_authority_operations_channel_denied(self):
        assert can_subscribe_to_channel("user_1", "tourist", "authority:operations") is False

    def test_authority_operations_channel_allowed(self):
        assert can_subscribe_to_channel("auth_1", "authority", "authority:operations") is True

    def test_admin_full_channel_access(self):
        assert can_subscribe_to_channel("admin_1", "admin", "authority:operations") is True
        assert can_subscribe_to_channel("admin_1", "admin", "user:user_random") is True
        assert can_subscribe_to_channel("admin_1", "admin", "tourist:any_id") is True

    def test_zone_channel_open_to_all_authenticated(self):
        assert can_subscribe_to_channel("user_1", "tourist", "zone:zone_456") is True
        assert can_subscribe_to_channel("auth_1", "authority", "zone:zone_456") is True

    def test_invalid_channel_format_denied(self):
        assert can_subscribe_to_channel("user_1", "tourist", "invalidchannel") is False
        assert can_subscribe_to_channel("user_1", "tourist", "") is False

    def test_default_channels_generation(self):
        tourist_channels = get_default_channels("t_user", "tourist", {"id": "t_profile_1"})
        assert "user:t_user" in tourist_channels
        assert "tourist:t_profile_1" in tourist_channels

        auth_channels = get_default_channels("a_user", "authority", {"id": "a_profile_1"})
        assert "user:a_user" in auth_channels
        assert "authority:operations" in auth_channels
        assert "authority:a_profile_1" in auth_channels


@pytest.mark.asyncio
class TestConnectionManager:
    async def test_register_and_cleanup(self):
        mgr = ConnectionManager()
        mock_ws = AsyncMock()

        ctx = await mgr.register(
            websocket=mock_ws,
            user_id="user_test_1",
            role="tourist",
            initial_channels=["user:user_test_1", "zone:zone_100"],
        )

        assert ctx.connection_id in mgr._active_connections
        assert "user_test_1" in mgr._user_connections
        assert "tourist" in mgr._role_connections
        assert "zone:zone_100" in mgr._channel_subscribers

        # Test subscription
        await mgr.subscribe(ctx.connection_id, "zone:zone_200")
        assert "zone:zone_200" in ctx.channels
        assert "zone:zone_200" in mgr._channel_subscribers

        # Test unsubscribe
        await mgr.unsubscribe(ctx.connection_id, "zone:zone_100")
        assert "zone:zone_100" not in ctx.channels
        assert "zone:zone_100" not in mgr._channel_subscribers

        # Test disconnect cleanup
        disconnected = await mgr.disconnect(ctx.connection_id)
        assert disconnected.connection_id == ctx.connection_id
        assert ctx.connection_id not in mgr._active_connections
        assert "user_test_1" not in mgr._user_connections
        assert "tourist" not in mgr._role_connections
        assert "zone:zone_200" not in mgr._channel_subscribers

    async def test_send_envelope_success_and_failure(self):
        mgr = ConnectionManager()
        mock_ws = AsyncMock()
        ctx = await mgr.register(mock_ws, "user_test_2", "authority", ["authority:operations"])

        env = RealtimeEventEnvelope(event_type="alert.created", payload={"alert_id": "a_1"})
        sent = await mgr.send_envelope(ctx.connection_id, env)
        assert sent is True
        assert ctx.messages_sent == 1
        mock_ws.send_text.assert_called_once()

        # Simulate socket write failure causing auto-disconnect
        failing_ws = AsyncMock()
        failing_ws.send_text.side_effect = Exception("Broken pipe")
        ctx_fail = await mgr.register(failing_ws, "user_fail", "tourist", [])
        sent_fail = await mgr.send_envelope(ctx_fail.connection_id, env)
        assert sent_fail is False
        assert ctx_fail.connection_id not in mgr._active_connections


@pytest.mark.asyncio
class TestRealtimeEventBus:
    async def test_event_bus_publishing(self):
        mgr = ConnectionManager()
        bus = RealtimeEventBus(manager=mgr)

        ws_auth = AsyncMock()
        ctx_auth = await mgr.register(ws_auth, "auth_1", "authority", ["authority:operations"])

        ws_tourist = AsyncMock()
        ctx_tourist = await mgr.register(ws_tourist, "tourist_1", "tourist", ["user:tourist_1", "zone:z_1"])

        # Broadcast to authority
        env_auth = await bus.publish_event(
            event_type="alert.created",
            payload={"id": "alt_1"},
            channel="authority:operations",
        )
        assert env_auth.event_type == "alert.created"
        ws_auth.send_text.assert_called()
        ws_tourist.send_text.assert_not_called()

        # Broadcast to zone
        ws_auth.reset_mock()
        ws_tourist.reset_mock()
        await bus.publish_event(
            event_type="zone.updated",
            payload={"zone_id": "z_1"},
            channel="zone:z_1",
        )
        ws_tourist.send_text.assert_called()


class TestHealthEndpoint:
    def test_health_check_returns_healthy_or_degraded(self):
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unavailable"]
        assert "services" in data
        assert "backend" in data["services"]
        assert "mongodb" in data["services"]
        assert "redis" in data["services"]
        assert "realtime" in data["services"]
        assert data["services"]["realtime"]["transport"] == "websocket"


class TestRealtimeWebSocketE2E:
    def test_websocket_connection_unauthorized_rejected(self):
        client = TestClient(app)
        with client.websocket_connect("/ws?token=invalid_jwt_token") as ws:
            msg = ws.receive_json()
            assert msg["event_type"] == "system.disconnected"
            assert "Authentication failed" in msg["payload"]["reason"]

    def test_websocket_tourist_authenticated_lifecycle(self):
        client = TestClient(app)
        token = create_access_token(user_id="tourist_ws_1", role="tourist")

        with client.websocket_connect(f"/ws?token={token}") as ws:
            # 1. Expect connection ack
            ack = ws.receive_json()
            assert ack["event_type"] == "system.connected"
            assert ack["payload"]["user_id"] == "tourist_ws_1"
            assert ack["payload"]["role"] == "tourist"
            assert "user:tourist_ws_1" in ack["payload"]["channels"]

            # 2. Test Ping / Heartbeat
            ws.send_json({"action": "ping"})
            pong = ws.receive_json()
            assert pong["event_type"] == "system.heartbeat"
            assert pong["payload"]["type"] == "pong"

            # 3. Test Subscribe to authorized zone
            ws.send_json({"action": "subscribe", "channel": "zone:z_test_100"})
            sub_res = ws.receive_json()
            assert sub_res["event_type"] == "system.status"
            assert sub_res["payload"]["subscribed"] == "zone:z_test_100"

            # 4. Test Subscribe to unauthorized authority channel (Denied)
            ws.send_json({"action": "subscribe", "channel": "authority:operations"})
            denied_res = ws.receive_json()
            assert denied_res["event_type"] == "system.error"
            assert "denied" in denied_res["payload"]["error"]

    def test_websocket_authority_connection(self):
        client = TestClient(app)
        auth_token = create_access_token(user_id="auth_ws_1", role="authority")

        with client.websocket_connect(f"/ws?token={auth_token}") as ws:
            ack = ws.receive_json()
            assert ack["event_type"] == "system.connected"
            assert "authority:operations" in ack["payload"]["channels"]

            # Test Subscribe to incident channel
            ws.send_json({"action": "subscribe", "channel": "incident:inc_999"})
            inc_res = ws.receive_json()
            assert inc_res["event_type"] == "system.status"
            assert inc_res["payload"]["subscribed"] == "incident:inc_999"

    def test_dev_test_event_api_endpoint(self):
        client = TestClient(app)
        auth_token = create_access_token(user_id="dev_user_1", role="admin")
        headers = {"Authorization": f"Bearer {auth_token}"}

        post_res = client.post(
            "/api/v1/dev/realtime/test-event",
            headers=headers,
            json={
                "event_type": "zone.status_changed",
                "channel": "zone:zone_456",
                "payload": {"zone_id": "zone_456", "status": "warning"},
            },
        )
        assert post_res.status_code == 200
        posted_data = post_res.json()
        assert posted_data["event_type"] == "zone.status_changed"
        assert posted_data["payload"]["zone_id"] == "zone_456"
        assert posted_data["version"] == 1
        assert posted_data["source"] == "dev_test:dev_user_1"

        # Check stats endpoint
        stats_res = client.get("/api/v1/dev/realtime/stats", headers=headers)
        assert stats_res.status_code == 200
        stats_data = stats_res.json()
        assert "active_connections" in stats_data
        assert "channels" in stats_data

