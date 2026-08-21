"""
TourSafe - Geofencing Realtime Event Publisher & Deduplication

Dispatches canonical realtime events:
- zone.entered
- zone.exited
- zone.dwell.threshold_reached
- zone.membership.uncertain
- zone.membership.stale

Enforces deduplication to prevent repeated events for the same transition.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set
import uuid

from ...schemas.realtime import RealtimeEventEnvelope
from ...services.realtime_bus import realtime_bus
from .types import ActiveZoneMembership, ContainmentResult

logger = logging.getLogger("toursafe.geofencing.events")

# In-memory deduplication cache: set of event deduplication keys
_emitted_event_keys: Set[str] = set()
_MAX_DEDUP_CACHE_SIZE = 10000


class GeofenceEventPublisher:
    """
    Constructs and broadcasts canonical zone events over Redis/WebSocket realtime bus.
    """

    @staticmethod
    def _make_dedup_key(tourist_id: str, zone_id: str, event_type: str, timestamp_str: str) -> str:
        # Deduplication key windowing to second precision
        return f"{tourist_id}:{zone_id}:{event_type}:{timestamp_str[:19]}"

    @classmethod
    async def publish_zone_event(
        cls,
        event_type: str,
        tourist_id: str,
        user_id: str,
        zone: Dict[str, Any],
        location_sample: Any,
        containment: ContainmentResult,
        membership: Optional[ActiveZoneMembership] = None,
        dwell_duration_seconds: Optional[float] = None,
    ) -> Optional[RealtimeEventEnvelope]:
        """
        Builds canonical event envelope, deduplicates, and broadcasts to tourist & authority channels.
        """
        zone_id = zone.get("zone_id") or zone.get("id") or "unknown_zone"
        zone_name = zone.get("name", zone_id)
        zone_type = zone.get("zone_type", "safe")
        risk_level = zone.get("risk_level", "low")
        sample_ts = getattr(location_sample, "timestamp", None) or datetime.now(timezone.utc).isoformat()
        session_id = getattr(location_sample, "session_id", None)

        dedup_key = cls._make_dedup_key(tourist_id, zone_id, event_type, sample_ts)
        if dedup_key in _emitted_event_keys:
            logger.debug("Deduplicating duplicate zone event: %s", dedup_key)
            return None

        _emitted_event_keys.add(dedup_key)
        if len(_emitted_event_keys) > _MAX_DEDUP_CACHE_SIZE:
            # Prune oldest items
            for _ in range(1000):
                _emitted_event_keys.pop()

        lat = getattr(location_sample, "latitude", 0.0)
        lon = getattr(location_sample, "longitude", 0.0)
        acc = getattr(location_sample, "accuracy", 10.0)

        # Build payload
        payload: Dict[str, Any] = {
            "tourist_id": tourist_id,
            "zone_id": zone_id,
            "zone_name": zone_name,
            "zone_type": zone_type,
            "risk_level": risk_level,
            "event_type": event_type,
            "timestamp": sample_ts,
            "session_id": session_id,
            "location": {
                "latitude": lat,
                "longitude": lon,
            },
            "accuracy": round(acc, 2) if acc is not None else None,
            "confidence_score": containment.confidence_score,
            "confidence_level": containment.confidence_level.value if hasattr(containment.confidence_level, "value") else str(containment.confidence_level),
            "distance_to_boundary_m": containment.distance_to_boundary_meters,
        }

        if dwell_duration_seconds is not None:
            payload["dwell_duration_seconds"] = round(dwell_duration_seconds, 1)
        elif membership and membership.dwell_duration_seconds > 0:
            payload["dwell_duration_seconds"] = round(membership.dwell_duration_seconds, 1)

        if membership and membership.entered_at:
            payload["entered_at"] = membership.entered_at

        # Tourist alert text
        alert_msg = zone.get("properties", {}).get("alert_message")
        if not alert_msg:
            if event_type == "zone.entered":
                if zone_type == "restricted":
                    alert_msg = f"Restricted Area: You have entered {zone_name}. Please proceed with caution."
                elif zone_type == "warning":
                    alert_msg = f"Caution: You have entered {zone_name}."
                else:
                    alert_msg = f"You have entered {zone_name}."
            elif event_type == "zone.exited":
                alert_msg = f"You have left {zone_name}."
            elif event_type == "zone.dwell.threshold_reached":
                alert_msg = f"Dwell Notice: You have been in {zone_name} for extended duration."

        payload["message"] = alert_msg

        envelope = RealtimeEventEnvelope(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            source="geofence_engine",
            version=1,
            payload=payload,
        )

        # Broadcast to tourist private channel and authority operations channel
        try:
            await realtime_bus.publish_to_channel(f"tourist:{tourist_id}", envelope)
            await realtime_bus.publish_to_channel("authority:operations", envelope)
            logger.info("Broadcasted %s for tourist %s in zone %s", event_type, tourist_id, zone_id)
        except Exception as e:
            logger.warning("Realtime event broadcast warning for %s: %s", event_type, e)

        return envelope


geofence_event_publisher = GeofenceEventPublisher()
