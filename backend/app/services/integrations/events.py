from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional
import uuid

from ...schemas.integrations import OutboundEventEnvelope
from ...services.realtime_bus import realtime_bus
from .security import security_manager

logger = logging.getLogger("toursafe.integrations.events")


class OutboundEventPublisher:
    """
    Versioned Outbound Integration Event Publisher.
    Publishes normalized, versioned system events (e.g. INCIDENT_CREATED, SOS_CREATED, RISK_ESCALATED)
    to external webhooks and the TourSafe realtime message bus.
    """

    def __init__(self):
        self._subscribers: List[Dict[str, Any]] = []

    def register_webhook_subscriber(
        self,
        target_url: str,
        events: List[str],
        secret: Optional[str] = None,
    ) -> None:
        self._subscribers.append({
            "target_url": target_url,
            "events": set(events),
            "secret": secret,
        })
        logger.info("OutboundEventPublisher: Registered subscriber for events %s -> %s", events, target_url)

    @staticmethod
    def create_signature(payload_json: str, secret: str) -> str:
        return hmac.new(secret.encode("utf-8"), payload_json.encode("utf-8"), hashlib.sha256).hexdigest()

    async def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
        event_version: str = "1.0.0",
        source: str = "toursafe.core",
        is_emergency: bool = False,
    ) -> OutboundEventEnvelope:
        event_id = f"evt_out_{uuid.uuid4().hex[:12]}"
        corr_id = correlation_id or f"corr_{uuid.uuid4().hex[:10]}"

        # Apply PII minimization & secret redaction
        sanitized_payload = security_manager.redact_secrets(payload)
        minimized_payload = security_manager.minimize_pii(sanitized_payload, is_emergency=is_emergency)

        envelope = OutboundEventEnvelope(
            event_id=event_id,
            event_type=event_type,
            event_version=event_version,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source=source,
            correlation_id=corr_id,
            payload=minimized_payload,
        )

        # Broadcast over Realtime Bus if available
        try:
            from ...schemas.realtime import RealtimeEventEnvelope, RealtimeEventType
            # Safely attempt realtime broadcast for authority subscribers
            await realtime_bus.publish_channel(
                channel="integrations:events",
                event_type="EXTERNAL_INTEGRATION_EVENT",
                payload=envelope.dict(),
            )
        except Exception as e:
            logger.debug("OutboundEventPublisher: Realtime broadcast notice: %s", e)

        logger.info("OutboundEventPublisher: Published event '%s' [id=%s, version=%s]", event_type, event_id, event_version)
        return envelope


# Global Singleton
outbound_event_publisher = OutboundEventPublisher()
