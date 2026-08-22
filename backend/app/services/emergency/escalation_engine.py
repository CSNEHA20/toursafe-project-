"""
TourSafe Durable Emergency Escalation Engine

Executes versioned escalation policy (emergency_escalation_v1.yaml)
with durable stage idempotency and role-based operational notifications.
"""

from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from ...core import database as db_core


def get_database():
    return db_core.get_database()
from ...schemas.emergency import (
    IncidentSeverity,
    IncidentStatus,
    NotificationChannel,
    TimelineEventRecord,
)
from ...schemas.safety import IncidentRecord
from .notifications import notification_service

logger = logging.getLogger("toursafe.emergency.escalation")


class EscalationConfigLoader:
    """
    Loads and caches versioned YAML escalation policies.
    """

    DEFAULT_POLICY = {
        "policy_version": "emergency-escalation-v1",
        "thresholds": {
            "acknowledgement_timeout_seconds": 120,
            "assignment_timeout_seconds": 300,
            "response_timeout_seconds": 600,
        },
        "stages": [
            {
                "stage": 1,
                "trigger": "UNACKNOWLEDGED_TIMEOUT",
                "name": "Tier 1 Urgent Alert",
                "escalate_severity_to": "HIGH",
                "notify_roles": ["authority", "lead_operator"],
                "channels": ["PUSH", "EMAIL"],
                "description": "Incident unacknowledged past timeout threshold.",
            },
            {
                "stage": 2,
                "trigger": "UNASSIGNED_TIMEOUT",
                "name": "Tier 2 Supervisor Escalation",
                "escalate_severity_to": "CRITICAL",
                "notify_roles": ["authority_supervisor", "district_commander"],
                "channels": ["PUSH", "SMS", "EMAIL"],
                "description": "Incident acknowledged but unassigned past timeout threshold.",
            },
            {
                "stage": 3,
                "trigger": "RESPONSE_DELAY_TIMEOUT",
                "name": "Tier 3 Regional Command Escalation",
                "escalate_severity_to": "CRITICAL",
                "notify_roles": ["regional_director", "emergency_coordinator"],
                "channels": ["PUSH", "SMS", "VOICE"],
                "description": "Response delay past timeout threshold.",
            },
        ],
        "emergency_contacts": {
            "min_severity_for_dispatch": "HIGH",
            "allowed_channels": ["SMS", "EMAIL"],
        },
    }

    @classmethod
    def load(cls) -> Dict[str, Any]:
        yaml_path = Path(__file__).resolve().parent.parent.parent / "core" / "emergency_escalation_v1.yaml"
        if yaml_path.exists():
            try:
                with open(yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data and isinstance(data, dict):
                        return data
            except Exception as e:
                logger.warning("Failed to parse %s, falling back to default: %s", yaml_path, e)
        return cls.DEFAULT_POLICY


class EscalationEngine:
    """
    Durable escalation evaluator and scheduler.
    """

    def __init__(self):
        self.policy = EscalationConfigLoader.load()
        self.policy_version = self.policy.get("policy_version", "emergency-escalation-v1")
        self.thresholds = self.policy.get("thresholds", {})
        self.stages = self.policy.get("stages", [])

    def reload_policy(self):
        self.policy = EscalationConfigLoader.load()
        self.policy_version = self.policy.get("policy_version", "emergency-escalation-v1")
        self.thresholds = self.policy.get("thresholds", {})
        self.stages = self.policy.get("stages", [])

    async def evaluate_incident_escalation(
        self,
        incident: IncidentRecord,
        override_now: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates whether an incident qualifies for stage-based operational escalation.
        Enforces idempotency keys: f"{incident_id}:{stage}:{policy_version}".
        """
        now = override_now or datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # Terminal or resolved incidents never escalate
        st_val = incident.status.value if hasattr(incident.status, "value") else str(incident.status)
        if st_val in (IncidentStatus.RESOLVED.value, IncidentStatus.CANCELLED.value, IncidentStatus.CLOSED.value):
            return None

        # Calculate time in current phase
        ack_timeout = self.thresholds.get("acknowledgement_timeout_seconds", 120)
        assign_timeout = self.thresholds.get("assignment_timeout_seconds", 300)
        resp_timeout = self.thresholds.get("response_timeout_seconds", 600)

        started_dt = datetime.fromisoformat(incident.started_at.replace("Z", "+00:00"))
        time_since_start = (now - started_dt).total_seconds()

        eligible_stage = None

        # Stage 1: Unacknowledged OPEN incident
        if st_val == IncidentStatus.OPEN.value and time_since_start >= ack_timeout:
            eligible_stage = self.stages[0] if len(self.stages) > 0 else None

        # Stage 2: Acknowledged / Assessing but unassigned
        elif st_val in (IncidentStatus.ACKNOWLEDGED.value, IncidentStatus.ASSESSING.value):
            ack_dt = datetime.fromisoformat((incident.acknowledged_at or incident.started_at).replace("Z", "+00:00"))
            time_since_ack = (now - ack_dt).total_seconds()
            if time_since_ack >= assign_timeout:
                eligible_stage = self.stages[1] if len(self.stages) > 1 else None

        # Stage 3: Assigned / Responding with response timeout
        elif st_val in (IncidentStatus.ASSIGNED.value, IncidentStatus.RESPONDING.value):
            updated_dt = datetime.fromisoformat(incident.updated_at.replace("Z", "+00:00"))
            time_since_update = (now - updated_dt).total_seconds()
            if time_since_update >= resp_timeout:
                eligible_stage = self.stages[2] if len(self.stages) > 2 else None

        if not eligible_stage:
            return None

        stage_num = eligible_stage["stage"]
        idempotency_key = f"{incident.incident_id}:{stage_num}:{self.policy_version}"

        # Check if already executed
        existing_keys = {entry.get("idempotency_key") for entry in incident.escalation_history}
        if idempotency_key in existing_keys:
            return None  # Idempotent skip

        # Execute escalation
        target_sev_str = eligible_stage.get("escalate_severity_to", "HIGH")
        target_severity = IncidentSeverity[target_sev_str] if target_sev_str in IncidentSeverity.__members__ else IncidentSeverity.HIGH

        escalation_entry = {
            "idempotency_key": idempotency_key,
            "stage": stage_num,
            "stage_name": eligible_stage.get("name"),
            "policy_version": self.policy_version,
            "triggered_at": now_iso,
            "reason": eligible_stage.get("description"),
            "target_severity": target_severity.value,
        }

        # Update incident record
        prev_state = st_val
        incident.status = IncidentStatus.ESCALATED
        incident.severity = target_severity
        incident.escalation_stage = stage_num
        incident.escalation_history.append(escalation_entry)
        incident.updated_at = now_iso
        incident.version += 1

        # Add timeline event
        tle = TimelineEventRecord(
            incident_id=incident.incident_id,
            timestamp=now_iso,
            actor_type="SYSTEM",
            actor_id="escalation_engine",
            action="incident.escalated",
            previous_state=prev_state,
            new_state=IncidentStatus.ESCALATED.value,
            metadata=escalation_entry,
            reason=f"Automated policy escalation Stage {stage_num}: {eligible_stage.get('name')}",
        )
        incident.timeline.append(tle.model_dump())

        # Notify operational channels
        roles = eligible_stage.get("notify_roles", ["authority"])
        for role in roles:
            for ch_str in eligible_stage.get("channels", ["PUSH"]):
                if ch_str in NotificationChannel.__members__:
                    channel = NotificationChannel[ch_str]
                    await notification_service.send_notification(
                        recipient=f"role:{role}",
                        channel=channel,
                        subject=f"URGENT: Incident {incident.incident_id} Escalated (Stage {stage_num})",
                        message=f"Incident {incident.incident_id} escalated to {target_severity.value}. Reason: {eligible_stage.get('description')}",
                        incident_id=incident.incident_id,
                        recipient_type="AUTHORITY_CENTER",
                        policy_trigger=idempotency_key,
                    )

        # Update in Mongo
        db = get_database()
        await db.incidents.replace_one({"incident_id": incident.incident_id}, incident.model_dump(), upsert=True)

        return escalation_entry

    async def run_escalation_sweep(self) -> int:
        """
        Durable sweep across all active incidents.
        Can be invoked periodically by a background worker or cron task.
        """
        db = get_database()
        active_statuses = [
            IncidentStatus.OPEN.value,
            IncidentStatus.ACKNOWLEDGED.value,
            IncidentStatus.ASSESSING.value,
            IncidentStatus.ASSIGNED.value,
            IncidentStatus.RESPONDING.value,
        ]
        cursor = db.incidents.find({"status": {"$in": active_statuses}})
        escalated_count = 0
        async for doc in cursor:
            try:
                inc = IncidentRecord(**doc)
                res = await self.evaluate_incident_escalation(inc)
                if res:
                    escalated_count += 1
            except Exception as e:
                logger.error("Error evaluating escalation for incident %s: %s", doc.get("incident_id"), e)

        return escalated_count


escalation_engine = EscalationEngine()
