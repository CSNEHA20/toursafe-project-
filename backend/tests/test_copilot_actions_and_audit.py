"""
Tests for Human-in-the-Loop Action Confirmations, Token Expiry,
Idempotency, Audit Logging, and Performance Metrics.
"""

from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import get_database
from app.core.security import create_access_token
from app.models.copilot import ActionStatus, FeedbackRating
from app.services.copilot.action_manager import action_manager
from app.services.copilot.audit_service import copilot_audit_service
from app.services.copilot.test_utils import setup_mock_db



@pytest.fixture(autouse=True)
def mock_db_fixture(monkeypatch):
    return setup_mock_db(monkeypatch)


@pytest.fixture
def auth_headers():

    token = create_access_token(user_id="usr_auth_op_1", role="authority")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    token = create_access_token(user_id="usr_admin_op_1", role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def tourist_headers():
    token = create_access_token(user_id="usr_tourist_hacker", role="tourist")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_01_action_proposal_and_preview_workflow(auth_headers):
    """Verify action proposal creates preview with token and expires_at."""
    proposal = await action_manager.propose_action(
        session_id="ses_test_action_1",
        user_id="usr_auth_op_1",
        tool_name="propose_dispatch_responder",
        action_type="dispatch_responder",
        target_id="inc_sample_101",
        target_description="Unit 12 to Incident inc_sample_101",
        reason="Elevated risk episode in dangerous tidal sector",
        expected_effect="Assigns Unit 12 and activates 180s SLA timer.",
        parameters={"incident_id": "inc_sample_101", "responder_id": "resp_unit_12"},
    )
    assert proposal.status == ActionStatus.PENDING
    assert proposal.confirmation_token.startswith("tok_")
    assert proposal.expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_02_action_confirmation_and_idempotency(auth_headers):
    """Verify confirming action with valid token executes action, and repeated confirm is idempotent."""
    proposal = await action_manager.propose_action(
        session_id="ses_test_action_2",
        user_id="usr_auth_op_1",
        tool_name="propose_dispatch_responder",
        action_type="dispatch_responder",
        target_id="inc_sample_102",
        target_description="Unit 14 to Incident inc_sample_102",
        reason="Operator requested dispatch",
        expected_effect="Assigns Unit 14",
        parameters={"incident_id": "inc_sample_102", "responder_id": "resp_unit_14"},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. First confirmation
        res_confirm = await client.post(
            f"/api/v1/copilot/actions/{proposal.action_id}/confirm",
            headers=auth_headers,
            json={"confirmation_token": proposal.confirmation_token},
        )
        assert res_confirm.status_code == 200
        confirm_data = res_confirm.json()
        assert confirm_data["status"] == "confirmed"

        # 2. Replay same confirmation (Idempotent execution)
        res_replay = await client.post(
            f"/api/v1/copilot/actions/{proposal.action_id}/confirm",
            headers=auth_headers,
            json={"confirmation_token": proposal.confirmation_token},
        )
        assert res_replay.status_code == 200
        assert res_replay.json()["status"] == "confirmed"
        assert "idempotent" in res_replay.json()["message"].lower()


@pytest.mark.asyncio
async def test_03_action_cancellation(auth_headers):
    """Verify operator can cancel an action proposal without side effects."""
    proposal = await action_manager.propose_action(
        session_id="ses_test_action_3",
        user_id="usr_auth_op_1",
        tool_name="propose_escalate_incident",
        action_type="escalate_incident",
        target_id="inc_sample_103",
        target_description="Escalate Incident inc_sample_103",
        reason="Manual escalation review",
        expected_effect="Triggers stage 2 escalation",
        parameters={"incident_id": "inc_sample_103"},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/copilot/actions/{proposal.action_id}/cancel",
            headers=auth_headers,
            json={"reason_note": "False alarm confirmed by tourist"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_04_action_token_expiry_rejection(auth_headers):
    """Verify expired confirmation tokens are rejected."""
    proposal = await action_manager.propose_action(
        session_id="ses_test_action_4",
        user_id="usr_auth_op_1",
        tool_name="propose_dispatch_responder",
        action_type="dispatch_responder",
        target_id="inc_sample_104",
        target_description="Unit 99 to Incident inc_sample_104",
        reason="Test expired token",
        expected_effect="Test",
        parameters={},
    )

    # Manually expire the action in DB
    db = get_database()
    past_iso = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    await db["copilot_actions"].update_one(
        {"action_id": proposal.action_id},
        {"$set": {"expires_at": past_iso}},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/copilot/actions/{proposal.action_id}/confirm",
            headers=auth_headers,
            json={"confirmation_token": proposal.confirmation_token},
        )
        assert res.status_code == 400
        assert "expired" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_05_unauthorized_action_confirmation_blocked(tourist_headers):
    """Verify unauthorized roles (e.g. tourist) cannot confirm operational actions."""
    proposal = await action_manager.propose_action(
        session_id="ses_test_action_5",
        user_id="usr_auth_op_1",
        tool_name="propose_dispatch_responder",
        action_type="dispatch_responder",
        target_id="inc_sample_105",
        target_description="Unit 99 to Incident inc_sample_105",
        reason="Test unauthorized confirmation",
        expected_effect="Test",
        parameters={},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/copilot/actions/{proposal.action_id}/confirm",
            headers=tourist_headers,
            json={"confirmation_token": proposal.confirmation_token},
        )
        assert res.status_code == 400
        assert "not authorized" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_06_feedback_and_metrics_endpoints(admin_headers, auth_headers):
    """Verify feedback submission, audit logging, and metrics aggregation endpoints."""
    # Log an audit event
    await copilot_audit_service.log_event(
        user_id="usr_auth_op_1",
        session_id="ses_aud_1",
        role="authority",
        action="query_completed",
        tool_name="get_active_incidents",
        latency_ms=85.0,
    )

    # Insert a dummy message to receive feedback
    db = get_database()
    msg_id = "msg_fb_test_1"
    await db["copilot_messages"].delete_many({"message_id": msg_id})
    await db["copilot_messages"].insert_one({
        "message_id": msg_id,
        "session_id": "ses_aud_1",
        "role": "ASSISTANT",
        "content": "Test response",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Submit feedback
        res_fb = await client.post(
            f"/api/v1/copilot/messages/{msg_id}/feedback",
            headers=auth_headers,
            json={"rating": "HELPFUL", "reason": "Accurate risk assessment"},
        )
        assert res_fb.status_code == 200
        assert res_fb.json()["status"] == "success"

        # 2. Get metrics (admin role)
        res_metrics = await client.get("/api/v1/copilot/metrics", headers=admin_headers)
        assert res_metrics.status_code == 200
        metrics = res_metrics.json()
        assert "total_messages" in metrics
        assert "tools_usage_count" in metrics

        # 3. Get audit logs (admin role)
        res_audit = await client.get("/api/v1/copilot/audit", headers=admin_headers)
        assert res_audit.status_code == 200
        assert len(res_audit.json()) >= 1
