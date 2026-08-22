"""
TourSafe Safety & Incident Realtime Event Publisher

Dispatches typed WebSocket event envelopes via RealtimeEventBus:
- safety.state.changed (to authority:operations & tourist:{tourist_id})
- incident.created (to authority:operations)
- incident.updated (to authority:operations)
- incident.resolved (to authority:operations)
"""

import logging
from typing import Any, Dict, Optional

from ...schemas.realtime import RealtimeEventEnvelope, RealtimeEventType
from ...schemas.safety import IncidentRecord, SafetyDecision, SafetyState
from ..realtime_bus import realtime_bus

logger = logging.getLogger("toursafe.safety.events")


def map_tourist_guidance(state: SafetyState, reasons: list) -> Tuple_Guidance:
    """Generates calm, user-appropriate guidance text for the tourist without leaking ML scores or rule IDs."""
    if state == SafetyState.NORMAL:
        return "Safety monitoring active. Your trip is proceeding normally.", "Normal"
    elif state == SafetyState.WATCH:
        return "TourSafe monitoring active. Please stay alert to your surroundings.", "Monitoring"
    elif state == SafetyState.ELEVATED:
        return "Attention: You are in an area requiring heightened caution. Check your map and stay on designated paths.", "Attention Required"
    elif state in (SafetyState.INCIDENT_CANDIDATE, SafetyState.INCIDENT):
        return "Safety alert detected. If you need assistance, please contact local emergency contacts or authorities.", "Assistance Available"
    elif state == SafetyState.RECOVERING:
        return "Safety condition clearing. Resuming normal monitoring.", "Monitoring"
    else:
        return "Location/telemetry signal temporarily degraded. Reconnecting...", "Reconnecting"


Tuple_Guidance = tuple[str, str]


class SafetyEventPublisher:
    """
    Publishes safety state changes and incident lifecycle events.
    """

    async def publish_state_changed(
        self,
        decision: SafetyDecision,
        user_id: Optional[str] = None,
    ) -> None:
        """Broadcasts safety.state.changed to authority and tourist channels."""
        # 1. Authority Operations Payload (Full operational detail)
        auth_payload = {
            "tourist_id": decision.tourist_id,
            "session_id": decision.session_id,
            "state": decision.state.value,
            "previous_state": decision.previous_state.value,
            "decision_id": decision.decision_id,
            "rule_version": decision.rule_version,
            "confidence_class": decision.confidence_class.value,
            "quality": decision.quality.value,
            "reasons": decision.reasons,
            "triggered_rules": [r.model_dump() for r in decision.triggered_rules],
            "signals": decision.signals,
            "timestamp": decision.timestamp,
        }

        envelope_auth = RealtimeEventEnvelope(
            event_type=RealtimeEventType.SAFETY_STATE_CHANGED.value,
            source="safety_orchestrator",
            payload=auth_payload,
        )

        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope_auth)
        except Exception as e:
            logger.warning("Failed to broadcast safety.state.changed to authority: %s", e)

        # 2. Tourist Payload (Sanitized and user-friendly)
        guidance, status_label = map_tourist_guidance(decision.state, decision.reasons)
        tourist_payload = {
            "tourist_id": decision.tourist_id,
            "safety_status": status_label,
            "monitoring_active": decision.state != SafetyState.UNKNOWN,
            "gps_connected": decision.quality != "UNKNOWN",
            "timestamp": decision.timestamp,
            "guidance_message": guidance,
        }

        envelope_tourist = RealtimeEventEnvelope(
            event_type=RealtimeEventType.SAFETY_STATE_CHANGED.value,
            source="safety_orchestrator",
            payload=tourist_payload,
        )

        try:
            await realtime_bus.publish_to_channel(f"tourist:{decision.tourist_id}", envelope_tourist)
            if user_id:
                await realtime_bus.broadcast_to_user(user_id, envelope_tourist)
        except Exception as e:
            logger.warning("Failed to broadcast safety.state.changed to tourist: %s", e)

    async def publish_incident_created(self, incident: IncidentRecord) -> None:
        """Broadcasts incident.created to authority operations channel."""
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.INCIDENT_CREATED.value,
            source="safety_orchestrator",
            payload=incident.model_dump(),
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
            logger.info("Broadcasted incident.created [%s] for tourist %s", incident.incident_id, incident.tourist_id)
        except Exception as e:
            logger.warning("Failed to broadcast incident.created: %s", e)

    async def publish_incident_updated(self, incident: IncidentRecord) -> None:
        """Broadcasts incident.updated to authority operations channel."""
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.INCIDENT_UPDATED.value,
            source="safety_orchestrator",
            payload=incident.model_dump(),
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
            logger.info("Broadcasted incident.updated [%s] for tourist %s", incident.incident_id, incident.tourist_id)
        except Exception as e:
            logger.warning("Failed to broadcast incident.updated: %s", e)

    async def publish_incident_resolved(self, incident: IncidentRecord) -> None:
        """Broadcasts incident.resolved to authority operations channel."""
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.INCIDENT_RESOLVED.value,
            source="safety_orchestrator",
            payload=incident.model_dump(),
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
            logger.info("Broadcasted incident.resolved [%s] for tourist %s", incident.incident_id, incident.tourist_id)
        except Exception as e:
            logger.warning("Failed to broadcast incident.resolved: %s", e)


safety_event_publisher = SafetyEventPublisher()
