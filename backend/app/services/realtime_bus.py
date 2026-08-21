import asyncio
import logging
from typing import Any, Dict, List, Optional

from ..core.connection_manager import connection_manager
from ..schemas.realtime import RealtimeEventEnvelope, RealtimeEventType

logger = logging.getLogger("toursafe.realtime.bus")


class RealtimeEventBus:
    """
    Centralized Realtime Event Bus for TourSafe.
    Decouples domain modules (zones, alerts, tourists, emergency) from
    the underlying WebSocket connections and channel routing.
    """

    def __init__(self, manager=connection_manager):
        self.manager = manager

    async def publish_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        channel: Optional[str] = None,
        target_user_id: Optional[str] = None,
        target_role: Optional[str] = None,
        source: str = "backend",
        version: int = 1,
    ) -> RealtimeEventEnvelope:
        """
        Create and dispatch a canonical RealtimeEventEnvelope.
        Can route by channel, user, role, or broadcast.
        """
        envelope = RealtimeEventEnvelope(
            event_type=event_type,
            source=source,
            version=version,
            payload=payload,
        )

        logger.info(
            "Publishing realtime event [id=%s, type=%s, channel=%s, target_user=%s, target_role=%s]",
            envelope.event_id,
            envelope.event_type,
            channel,
            target_user_id,
            target_role,
        )

        # Dispatch based on targeting
        if channel:
            await self.broadcast_to_channel(channel, envelope)
        elif target_user_id:
            await self.broadcast_to_user(target_user_id, envelope)
        elif target_role:
            await self.broadcast_to_role(target_role, envelope)
        else:
            # Broadcast to all connected clients if no target specified
            stats = self.manager.get_stats()
            active_cids = list(self.manager._active_connections.keys())
            tasks = [self.manager.send_envelope(cid, envelope) for cid in active_cids]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        return envelope

    async def broadcast_to_channel(self, channel: str, envelope: RealtimeEventEnvelope) -> int:
        """Deliver envelope to all active subscribers of a specific channel."""
        subscribers = self.manager.get_channel_subscribers(channel)
        if not subscribers:
            logger.debug("No active subscribers for channel '%s'", channel)
            return 0

        tasks = [
            self.manager.send_envelope(ctx.connection_id, envelope)
            for ctx in subscribers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        delivered_count = sum(1 for r in results if r is True)
        logger.info(
            "Delivered event %s to %d/%d subscribers on channel '%s'",
            envelope.event_id,
            delivered_count,
            len(subscribers),
            channel,
        )
        return delivered_count

    publish_to_channel = broadcast_to_channel

    async def broadcast_to_authority(self, envelope: RealtimeEventEnvelope) -> int:
        """Deliver event to the authority operations channel."""
        return await self.broadcast_to_channel("authority:operations", envelope)

    async def broadcast_to_zone(self, zone_id: str, envelope: RealtimeEventEnvelope) -> int:
        """Deliver event to subscribers of a specific zone."""
        return await self.broadcast_to_channel(f"zone:{zone_id}", envelope)

    async def broadcast_to_user(self, user_id: str, envelope: RealtimeEventEnvelope) -> int:
        """Deliver event to all active device connections belonging to a user."""
        connections = self.manager.get_user_connections(user_id)
        if not connections:
            logger.debug("User %s has no active connections", user_id)
            return 0

        tasks = [
            self.manager.send_envelope(ctx.connection_id, envelope)
            for ctx in connections
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return sum(1 for r in results if r is True)

    async def send_to_tourist(self, tourist_id: str, envelope: RealtimeEventEnvelope) -> int:
        """Deliver event to a tourist channel."""
        return await self.broadcast_to_channel(f"tourist:{tourist_id}", envelope)

    async def broadcast_to_role(self, role: str, envelope: RealtimeEventEnvelope) -> int:
        """Deliver event to all active connections with a specific role."""
        connections = self.manager.get_role_connections(role)
        if not connections:
            return 0

        tasks = [
            self.manager.send_envelope(ctx.connection_id, envelope)
            for ctx in connections
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return sum(1 for r in results if r is True)

    async def send_to_connection(self, connection_id: str, envelope: RealtimeEventEnvelope) -> bool:
        """Deliver event directly to a specific connection."""
        return await self.manager.send_envelope(connection_id, envelope)


# Global event bus instance
realtime_bus = RealtimeEventBus()
