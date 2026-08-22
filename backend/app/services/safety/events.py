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
        """Broadcasts incident.created to authority operations channel and notification infrastructure."""
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

        try:
            from ..notifications import notification_center
            await notification_center.handle_domain_event(
                event_type="incident.created",
                payload=incident.model_dump(),
                incident_id=incident.incident_id,
                tourist_id=incident.tourist_id,
            )
        except Exception as e:
            logger.warning("Failed to process notification policy for incident.created: %s", e)

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

    async def publish_sos_created(self, sos_dict: Dict[str, Any], tourist_id: str) -> None:
        """Broadcasts sos.created to authority operations and tourist channel."""
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.SOS_CREATED.value,
            source="sos_service",
            payload=sos_dict,
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
            await realtime_bus.publish_to_channel(f"tourist:{tourist_id}", envelope)
        except Exception as e:
            logger.warning("Failed to broadcast sos.created: %s", e)

        try:
            from ..notifications import notification_center
            await notification_center.handle_domain_event(
                event_type="incident.created",
                payload=sos_dict,
                incident_id=sos_dict.get("incident_id"),
                tourist_id=tourist_id,
            )
        except Exception as e:
            logger.warning("Failed to process notification policy for sos.created: %s", e)

    async def publish_incident_acknowledged(self, incident: IncidentRecord) -> None:
        """Broadcasts incident.acknowledged to authority operations and tourist channels."""
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.INCIDENT_ACKNOWLEDGED.value,
            source="emergency_service",
            payload=incident.model_dump(),
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
            await realtime_bus.publish_to_channel(
                f"tourist:{incident.tourist_id}",
                RealtimeEventEnvelope(
                    event_type=RealtimeEventType.INCIDENT_ACKNOWLEDGED.value,
                    source="emergency_service",
                    payload={
                        "incident_id": incident.incident_id,
                        "status": "ACKNOWLEDGED",
                        "acknowledged_at": incident.acknowledged_at,
                        "message": "TourSafe command center has acknowledged your incident. Assistance is in progress.",
                    },
                ),
            )
        except Exception as e:
            logger.warning("Failed to broadcast incident.acknowledged: %s", e)

    async def publish_incident_assessing(self, incident: IncidentRecord) -> None:
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.INCIDENT_ASSESSING.value,
            source="emergency_service",
            payload=incident.model_dump(),
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
        except Exception as e:
            logger.warning("Failed to broadcast incident.assessing: %s", e)

    async def publish_incident_assigned(self, incident: IncidentRecord) -> None:
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.INCIDENT_ASSIGNED.value,
            source="emergency_service",
            payload=incident.model_dump(),
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
            await realtime_bus.publish_to_channel(
                f"tourist:{incident.tourist_id}",
                RealtimeEventEnvelope(
                    event_type=RealtimeEventType.INCIDENT_ASSIGNED.value,
                    source="emergency_service",
                    payload={
                        "incident_id": incident.incident_id,
                        "status": "ASSIGNED",
                        "responder_type": incident.responder_type,
                        "message": "A responder team has been assigned to your location.",
                    },
                ),
            )
        except Exception as e:
            logger.warning("Failed to broadcast incident.assigned: %s", e)

        try:
            from ..notifications import notification_center
            await notification_center.handle_domain_event(
                event_type="incident.assigned",
                payload=incident.model_dump(),
                incident_id=incident.incident_id,
                tourist_id=incident.tourist_id,
                responder_id=incident.assigned_responder_id,
                unit_id=incident.assigned_unit_id,
            )
        except Exception as e:
            logger.warning("Failed to process notification policy for incident.assigned: %s", e)

    async def publish_incident_response_started(self, incident: IncidentRecord) -> None:
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.INCIDENT_RESPONSE_STARTED.value,
            source="emergency_service",
            payload=incident.model_dump(),
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
            await realtime_bus.publish_to_channel(
                f"tourist:{incident.tourist_id}",
                RealtimeEventEnvelope(
                    event_type=RealtimeEventType.INCIDENT_RESPONSE_STARTED.value,
                    source="emergency_service",
                    payload={
                        "incident_id": incident.incident_id,
                        "status": "RESPONDING",
                        "message": "Assistance team is actively responding.",
                    },
                ),
            )
        except Exception as e:
            logger.warning("Failed to broadcast incident.response.started: %s", e)

    async def publish_incident_escalated(self, incident: IncidentRecord) -> None:
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.INCIDENT_ESCALATED.value,
            source="emergency_service",
            payload=incident.model_dump(),
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
        except Exception as e:
            logger.warning("Failed to broadcast incident.escalated: %s", e)

        try:
            from ..notifications import notification_center
            await notification_center.handle_domain_event(
                event_type="incident.escalated",
                payload=incident.model_dump(),
                incident_id=incident.incident_id,
                tourist_id=incident.tourist_id,
            )
        except Exception as e:
            logger.warning("Failed to process notification policy for incident.escalated: %s", e)

    async def publish_incident_note_added(self, incident_id: str, note_dict: Dict[str, Any]) -> None:
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.INCIDENT_NOTE_ADDED.value,
            source="emergency_service",
            payload={"incident_id": incident_id, "note": note_dict},
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
        except Exception as e:
            logger.warning("Failed to broadcast incident.note.added: %s", e)

    async def publish_incident_location_updated(self, incident_id: str, location_dict: Dict[str, Any]) -> None:
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.INCIDENT_LOCATION_UPDATED.value,
            source="emergency_service",
            payload={"incident_id": incident_id, "location": location_dict},
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
        except Exception as e:
            logger.warning("Failed to broadcast incident.location.updated: %s", e)

    async def publish_incident_severity_changed(self, incident: IncidentRecord, prev_severity: str) -> None:
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.INCIDENT_SEVERITY_CHANGED.value,
            source="emergency_service",
            payload={"incident_id": incident.incident_id, "severity": incident.severity.value, "previous_severity": prev_severity},
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
        except Exception as e:
            logger.warning("Failed to broadcast incident.severity.changed: %s", e)

    async def publish_incident_resolved(self, incident: IncidentRecord) -> None:
        """Broadcasts incident.resolved to authority operations and tourist channels."""
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.INCIDENT_RESOLVED.value,
            source="emergency_service",
            payload=incident.model_dump(),
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
            await realtime_bus.publish_to_channel(
                f"tourist:{incident.tourist_id}",
                RealtimeEventEnvelope(
                    event_type=RealtimeEventType.INCIDENT_RESOLVED.value,
                    source="emergency_service",
                    payload={
                        "incident_id": incident.incident_id,
                        "status": "RESOLVED",
                        "resolved_at": incident.resolved_at,
                        "message": "Your emergency incident has been resolved. You are marked safe.",
                    },
                ),
            )
            logger.info("Broadcasted incident.resolved [%s] for tourist %s", incident.incident_id, incident.tourist_id)
        except Exception as e:
            logger.warning("Failed to broadcast incident.resolved: %s", e)

        try:
            from ..notifications import notification_center
            await notification_center.handle_domain_event(
                event_type="incident.resolved",
                payload=incident.model_dump(),
                incident_id=incident.incident_id,
                tourist_id=incident.tourist_id,
            )
        except Exception as e:
            logger.warning("Failed to process notification policy for incident.resolved: %s", e)

    async def publish_incident_cancelled(self, incident: IncidentRecord) -> None:
        """Broadcasts incident.cancelled to authority operations and tourist channels."""
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.INCIDENT_CANCELLED.value,
            source="emergency_service",
            payload=incident.model_dump(),
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
            await realtime_bus.publish_to_channel(
                f"tourist:{incident.tourist_id}",
                RealtimeEventEnvelope(
                    event_type=RealtimeEventType.INCIDENT_CANCELLED.value,
                    source="emergency_service",
                    payload={
                        "incident_id": incident.incident_id,
                        "status": "CANCELLED",
                        "message": "Your incident request has been cancelled.",
                    },
                ),
            )
        except Exception as e:
            logger.warning("Failed to broadcast incident.cancelled: %s", e)

    async def publish_incident_closed(self, incident: IncidentRecord) -> None:
        """Broadcasts incident.closed to authority operations channel."""
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.INCIDENT_CLOSED.value,
            source="emergency_service",
            payload=incident.model_dump(),
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
        except Exception as e:
            logger.warning("Failed to broadcast incident.closed: %s", e)


safety_event_publisher = SafetyEventPublisher()
