import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from ...core import database as db_core
from ...schemas.telemetry import (
    SessionStatusEnum,
    TelemetryAckStatus,
    TelemetrySample,
    TelemetrySessionMetrics,
    TelemetrySessionResponse,
)

logger = logging.getLogger("toursafe.telemetry.session")


class SessionState:
    """In-memory active telemetry session tracker for fast sequence & gap arithmetic."""

    def __init__(self, session_id: str, tourist_id: str, user_id: str, device_id: Optional[str] = None):
        self.session_id = session_id
        self.tourist_id = tourist_id
        self.user_id = user_id
        self.device_id = device_id
        self.status = SessionStatusEnum.ACTIVE
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.ended_at: Optional[str] = None

        # Sequence management
        self.received_sequences: Set[int] = set()
        self.highest_sequence: int = 0
        self.highest_contiguous_sequence: int = 0
        self.seen_packet_ids: Set[str] = set()

        # Timestamps
        self.last_packet_timestamp: Optional[str] = None
        self.last_gps_timestamp: Optional[str] = None
        self.last_imu_timestamp: Optional[str] = None
        self.last_sample_dt: Optional[datetime] = None

        # Metrics
        self.total_packets: int = 0
        self.accepted_packets: int = 0
        self.duplicate_packets: int = 0
        self.invalid_packets: int = 0
        self.out_of_order_packets: int = 0
        self.estimated_missing_packets: int = 0
        self.reconnection_count: int = 0
        self.last_gap_duration_ms: float = 0.0

        # Windows
        self.window_count: int = 0
        self.valid_window_count: int = 0
        self.invalid_window_count: int = 0

    def update_highest_contiguous(self):
        """Advances the contiguous sequence watermark."""
        curr = self.highest_contiguous_sequence
        while (curr + 1) in self.received_sequences:
            curr += 1
        self.highest_contiguous_sequence = curr

    def process_sequence(self, packet_id: str, seq: int, sample_dt: datetime) -> TelemetryAckStatus:
        """
        Evaluates incoming sequence number and idempotency key.
        Distinguishes:
        - DUPLICATE (already seen packet_id or sequence)
        - ACCEPTED (in-order or out-of-order new packet)
        - OUT_OF_ORDER (new packet whose sequence < highest received)
        """
        self.total_packets += 1

        # Idempotency check
        if packet_id in self.seen_packet_ids or seq in self.received_sequences:
            self.duplicate_packets += 1
            return TelemetryAckStatus.DUPLICATE

        self.seen_packet_ids.add(packet_id)
        # Cap seen packet ids memory
        if len(self.seen_packet_ids) > 10000:
            self.seen_packet_ids = set(list(self.seen_packet_ids)[-5000:])

        # Calculate time gap
        if self.last_sample_dt:
            gap_ms = max(0.0, (sample_dt - self.last_sample_dt).total_seconds() * 1000.0)
            self.last_gap_duration_ms = gap_ms
        self.last_sample_dt = sample_dt

        # Check sequence order
        is_out_of_order = False
        if seq < self.highest_sequence:
            self.out_of_order_packets += 1
            is_out_of_order = True
        else:
            # Sequence jump / missing estimate
            if self.highest_sequence > 0 and seq > (self.highest_sequence + 1):
                gap = seq - (self.highest_sequence + 1)
                self.estimated_missing_packets += gap
            self.highest_sequence = seq

        self.received_sequences.add(seq)
        # Bounded sequence set retention
        if len(self.received_sequences) > 20000:
            min_keep = max(1, self.highest_contiguous_sequence - 1000)
            self.received_sequences = {s for s in self.received_sequences if s >= min_keep}

        self.update_highest_contiguous()
        self.accepted_packets += 1

        return TelemetryAckStatus.OUT_OF_ORDER if is_out_of_order else TelemetryAckStatus.ACCEPTED

    def to_metrics(self) -> TelemetrySessionMetrics:
        return TelemetrySessionMetrics(
            total_packets=self.total_packets,
            accepted_packets=self.accepted_packets,
            duplicate_packets=self.duplicate_packets,
            invalid_packets=self.invalid_packets,
            out_of_order_packets=self.out_of_order_packets,
            estimated_missing_packets=max(0, self.highest_sequence - len(self.received_sequences)),
            reconnection_count=self.reconnection_count,
            last_gap_duration_ms=round(self.last_gap_duration_ms, 2),
            last_sequence_number=self.highest_sequence,
            highest_contiguous_sequence=self.highest_contiguous_sequence,
            last_packet_timestamp=self.last_packet_timestamp,
            last_gps_timestamp=self.last_gps_timestamp,
            last_imu_timestamp=self.last_imu_timestamp,
            window_count=self.window_count,
            valid_window_count=self.valid_window_count,
            invalid_window_count=self.invalid_window_count,
        )


class TelemetrySessionManager:
    """Manages lifecycle and metrics of active telemetry sessions."""

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_session(
        self,
        session_id: str,
        tourist_id: str,
        user_id: str,
        device_id: Optional[str] = None,
    ) -> SessionState:
        async with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]

            # Try loading from MongoDB if existing
            db = db_core.get_database()
            doc = await db.telemetry_sessions.find_one({"session_id": session_id})
            if doc:
                state = SessionState(
                    session_id=session_id,
                    tourist_id=doc.get("tourist_id", tourist_id),
                    user_id=doc.get("user_id", user_id),
                    device_id=doc.get("device_id", device_id),
                )
                state.status = SessionStatusEnum(doc.get("status", "active"))
                state.started_at = doc.get("started_at", datetime.now(timezone.utc).isoformat())
                state.highest_sequence = doc.get("last_sequence_number", 0)
                state.highest_contiguous_sequence = doc.get("highest_contiguous_sequence", state.highest_sequence)
                self._sessions[session_id] = state
                return state

            # Create new
            state = SessionState(session_id, tourist_id, user_id, device_id)
            self._sessions[session_id] = state
            now_utc = datetime.now(timezone.utc).isoformat()

            try:
                await db.telemetry_sessions.insert_one({
                    "session_id": session_id,
                    "tourist_id": tourist_id,
                    "user_id": user_id,
                    "device_id": device_id,
                    "status": state.status.value,
                    "started_at": state.started_at,
                    "created_at": now_utc,
                    "updated_at": now_utc,
                })
            except Exception as e:
                logger.debug("Telemetry session insert note: %s", e)

            return state

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        async with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]

            db = db_core.get_database()
            doc = await db.telemetry_sessions.find_one({"session_id": session_id})
            if doc:
                state = SessionState(
                    session_id=session_id,
                    tourist_id=doc.get("tourist_id", ""),
                    user_id=doc.get("user_id", ""),
                    device_id=doc.get("device_id"),
                )
                state.status = SessionStatusEnum(doc.get("status", "stopped"))
                state.started_at = doc.get("started_at", "")
                state.ended_at = doc.get("ended_at")
                state.highest_sequence = doc.get("last_sequence_number", 0)
                self._sessions[session_id] = state
                return state
            return None

    async def stop_session(self, session_id: str, tourist_id: str) -> Optional[TelemetrySessionResponse]:
        async with self._lock:
            state = self._sessions.get(session_id)
            now_utc = datetime.now(timezone.utc).isoformat()
            if state:
                state.status = SessionStatusEnum.STOPPED
                state.ended_at = now_utc

            db = db_core.get_database()
            doc = await db.telemetry_sessions.find_one_and_update(
                {"session_id": session_id, "tourist_id": tourist_id},
                {
                    "$set": {
                        "status": SessionStatusEnum.STOPPED.value,
                        "ended_at": now_utc,
                        "updated_at": now_utc,
                        "metrics": state.to_metrics().model_dump() if state else {},
                    }
                },
                return_document=True,
            )

            if doc:
                return TelemetrySessionResponse(
                    session_id=session_id,
                    tourist_id=tourist_id,
                    user_id=doc.get("user_id", ""),
                    device_id=doc.get("device_id"),
                    status=SessionStatusEnum.STOPPED,
                    started_at=doc.get("started_at", now_utc),
                    ended_at=now_utc,
                    metrics=state.to_metrics() if state else TelemetrySessionMetrics(),
                )
            return None

    def get_active_sessions_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s.status == SessionStatusEnum.ACTIVE)


telemetry_session_manager = TelemetrySessionManager()
