import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket

from ..schemas.realtime import RealtimeEventEnvelope

logger = logging.getLogger("toursafe.realtime.manager")


class ConnectionContext:
    def __init__(
        self,
        connection_id: str,
        user_id: str,
        role: str,
        websocket: WebSocket,
        session_id: Optional[str] = None,
        user_profile: Optional[Dict[str, Any]] = None,
        channels: Optional[Set[str]] = None,
    ):
        self.connection_id = connection_id
        self.user_id = user_id
        self.role = role
        self.websocket = websocket
        self.session_id = session_id
        self.user_profile = user_profile or {}
        self.connected_at = datetime.now(timezone.utc).isoformat()
        self.channels: Set[str] = channels or set()
        self.last_ping_at = datetime.now(timezone.utc).isoformat()
        self.messages_sent = 0
        self.messages_received = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "user_id": self.user_id,
            "role": self.role,
            "session_id": self.session_id,
            "connected_at": self.connected_at,
            "channels": list(self.channels),
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
        }


class ConnectionManager:
    """
    Centralized Realtime WebSocket Connection Manager.
    Manages active socket contexts, channel mapping, multi-device tracking,
    and automatic cleanup of disconnected sockets.
    """

    def __init__(self):
        self._active_connections: Dict[str, ConnectionContext] = {}
        self._user_connections: Dict[str, Set[str]] = {}
        self._role_connections: Dict[str, Set[str]] = {}
        self._channel_subscribers: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        websocket: WebSocket,
        user_id: str,
        role: str,
        initial_channels: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> ConnectionContext:
        """Register a freshly authenticated WebSocket connection."""
        conn_id = f"conn_{uuid.uuid4().hex[:12]}"
        channels_set = set(initial_channels or [])

        ctx = ConnectionContext(
            connection_id=conn_id,
            user_id=user_id,
            role=role,
            websocket=websocket,
            session_id=session_id,
            user_profile=user_profile,
            channels=channels_set,
        )

        async with self._lock:
            self._active_connections[conn_id] = ctx

            # Map user -> connection
            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(conn_id)

            # Map role -> connection
            if role not in self._role_connections:
                self._role_connections[role] = set()
            self._role_connections[role].add(conn_id)

            # Map channels -> connection
            for ch in channels_set:
                if ch not in self._channel_subscribers:
                    self._channel_subscribers[ch] = set()
                self._channel_subscribers[ch].add(conn_id)

        logger.info(
            "Registered connection %s (user_id=%s, role=%s, channels=%d)",
            conn_id,
            user_id,
            role,
            len(channels_set),
        )
        return ctx

    async def disconnect(self, connection_id: str) -> Optional[ConnectionContext]:
        """
        Gracefully unregister and cleanup a connection across all indices.
        """
        async with self._lock:
            ctx = self._active_connections.pop(connection_id, None)
            if not ctx:
                return None

            # Remove from user map
            if ctx.user_id in self._user_connections:
                self._user_connections[ctx.user_id].discard(connection_id)
                if not self._user_connections[ctx.user_id]:
                    del self._user_connections[ctx.user_id]

            # Remove from role map
            if ctx.role in self._role_connections:
                self._role_connections[ctx.role].discard(connection_id)
                if not self._role_connections[ctx.role]:
                    del self._role_connections[ctx.role]

            # Remove from channels map
            for ch in ctx.channels:
                if ch in self._channel_subscribers:
                    self._channel_subscribers[ch].discard(connection_id)
                    if not self._channel_subscribers[ch]:
                        del self._channel_subscribers[ch]

        logger.info(
            "Disconnected and cleaned up connection %s (user_id=%s)",
            connection_id,
            ctx.user_id,
        )
        return ctx

    async def subscribe(self, connection_id: str, channel: str) -> bool:
        """Add a channel subscription to an active connection."""
        async with self._lock:
            ctx = self._active_connections.get(connection_id)
            if not ctx:
                return False

            ctx.channels.add(channel)
            if channel not in self._channel_subscribers:
                self._channel_subscribers[channel] = set()
            self._channel_subscribers[channel].add(connection_id)

        logger.debug("Connection %s subscribed to channel '%s'", connection_id, channel)
        return True

    async def unsubscribe(self, connection_id: str, channel: str) -> bool:
        """Remove a channel subscription from an active connection."""
        async with self._lock:
            ctx = self._active_connections.get(connection_id)
            if not ctx:
                return False

            ctx.channels.discard(channel)
            if channel in self._channel_subscribers:
                self._channel_subscribers[channel].discard(connection_id)
                if not self._channel_subscribers[channel]:
                    del self._channel_subscribers[channel]

        logger.debug("Connection %s unsubscribed from channel '%s'", connection_id, channel)
        return True

    def get_connection(self, connection_id: str) -> Optional[ConnectionContext]:
        return self._active_connections.get(connection_id)

    def get_user_connections(self, user_id: str) -> List[ConnectionContext]:
        conn_ids = self._user_connections.get(user_id, set())
        return [self._active_connections[cid] for cid in conn_ids if cid in self._active_connections]

    def get_role_connections(self, role: str) -> List[ConnectionContext]:
        conn_ids = self._role_connections.get(role, set())
        return [self._active_connections[cid] for cid in conn_ids if cid in self._active_connections]

    def get_channel_subscribers(self, channel: str) -> List[ConnectionContext]:
        conn_ids = self._channel_subscribers.get(channel, set())
        return [self._active_connections[cid] for cid in conn_ids if cid in self._active_connections]

    async def send_envelope(self, connection_id: str, envelope: RealtimeEventEnvelope) -> bool:
        """Deliver a formatted envelope directly to a specific connection."""
        ctx = self._active_connections.get(connection_id)
        if not ctx:
            return False

        try:
            payload_str = envelope.model_dump_json()
            await ctx.websocket.send_text(payload_str)
            ctx.messages_sent += 1
            return True
        except Exception as e:
            logger.warning(
                "Failed to send to connection %s: %s. Initiating disconnect.",
                connection_id,
                e,
            )
            await self.disconnect(connection_id)
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Return realtime telemetry / status metrics."""
        role_counts = {role: len(cids) for role, cids in self._role_connections.items()}
        return {
            "active_connections": len(self._active_connections),
            "unique_users": len(self._user_connections),
            "active_channels": len(self._channel_subscribers),
            "channels": list(self._channel_subscribers.keys()),
            "roles_connected": role_counts,
        }


# Global connection manager instance
connection_manager = ConnectionManager()
