"""
TourSafe Incident Operational Messaging Service

Coordinates mission-critical, secure, and attributed operational chat
between Authority operators and assigned Responders for specific incidents.
Provides persistent audit logging and realtime websocket synchronization.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from ...core import database as db_core
from ...schemas.emergency import OperationalMessageCreateRequest, OperationalMessageRecord
from ...schemas.realtime import RealtimeEventEnvelope, RealtimeEventType
from ...services.realtime_bus import realtime_bus


def get_database():
    return db_core.get_database()


logger = logging.getLogger("toursafe.emergency.messaging")


class MessagingService:
    """
    Manages incident operational messages.
    """

    async def send_message(
        self,
        incident_id: str,
        sender_id: str,
        sender_type: str,
        sender_name: Optional[str],
        req: OperationalMessageCreateRequest,
    ) -> OperationalMessageRecord:
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        message_id = f"msg_{uuid.uuid4().hex[:12]}"

        # Verify incident exists
        incident_doc = await db.incidents.find_one({"incident_id": incident_id})
        if not incident_doc:
            raise ValueError(f"Incident '{incident_id}' not found")

        record = OperationalMessageRecord(
            message_id=message_id,
            incident_id=incident_id,
            assignment_id=req.assignment_id,
            sender_id=sender_id,
            sender_type=sender_type,
            sender_name=sender_name,
            timestamp=now_iso,
            content=req.content,
            delivery_status="DELIVERED",
        )

        await db.incident_messages.insert_one(record.model_dump())

        # Publish realtime event
        await realtime_bus.publish_event(
            event_type=RealtimeEventType.RESPONDER_MESSAGE_SENT.value,
            payload=record.model_dump(),
            target_role="authority",
        )

        return record

    async def get_messages(
        self,
        incident_id: str,
        limit: int = 50,
        skip: int = 0,
    ) -> List[OperationalMessageRecord]:
        db = get_database()
        cursor = db.incident_messages.find({"incident_id": incident_id}).sort("timestamp", 1).skip(skip).limit(limit)
        items = []
        async for doc in cursor:
            items.append(OperationalMessageRecord(**doc))
        return items

    async def mark_messages_read(self, incident_id: str, reader_id: str) -> int:
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        res = await db.incident_messages.update_many(
            {
                "incident_id": incident_id,
                "sender_id": {"$ne": reader_id},
                "read_at": None,
            },
            {"$set": {"read_at": now_iso}}
        )
        return res.modified_count


messaging_service = MessagingService()
