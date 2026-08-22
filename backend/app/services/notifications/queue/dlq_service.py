from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from ....core import database as db_core
from ....schemas.notification import (
    DeadLetterRecord,
    DeliveryErrorCategory,
    NotificationRecord,
    NotificationStatus,
)

logger = logging.getLogger("toursafe.notifications.queue.dlq")


class DeadLetterQueueService:
    """
    Dead-Letter Queue (DLQ) Service.
    Stores notifications that exhausted retries or failed permanently.
    Provides administrative inspection, manual retry, and audit resolution.
    """

    def __init__(self):
        pass

    async def enqueue_dead_letter(
        self,
        notification: NotificationRecord,
        reason: str,
        last_error_code: Optional[str] = None,
        last_error_message: Optional[str] = None,
        last_error_category: Optional[DeliveryErrorCategory] = None,
    ) -> DeadLetterRecord:
        record = DeadLetterRecord(
            notification_id=notification.notification_id,
            event_id=notification.event_id,
            incident_id=notification.incident_id,
            recipient_id=notification.recipient_id,
            recipient_type=notification.recipient_type,
            channel=notification.channel,
            provider=notification.provider,
            attempts=notification.retry_count,
            last_error_code=last_error_code or notification.error_code,
            last_error_message=last_error_message or notification.error_message,
            last_error_category=last_error_category,
            payload_snapshot=notification.payload.model_dump(),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        try:
            db = db_core.get_database()
            await db.notification_dead_letters.insert_one(record.model_dump())
            logger.warning(
                "Enqueued notification %s to DLQ [reason=%s, channel=%s, attempts=%d]",
                notification.notification_id,
                reason,
                notification.channel.value,
                notification.retry_count,
            )
        except Exception as ex:
            logger.error("Failed to persist dead letter record %s: %s", record.dead_letter_id, ex)

        return record

    async def list_dead_letters(
        self,
        limit: int = 50,
        skip: int = 0,
        unresolved_only: bool = True,
    ) -> List[DeadLetterRecord]:
        try:
            db = db_core.get_database()
            query: Dict[str, Any] = {}
            if unresolved_only:
                query["resolved"] = False
            cursor = db.notification_dead_letters.find(query).sort("timestamp", -1).skip(skip).limit(limit)
            docs = await cursor.to_list(length=limit)
            return [DeadLetterRecord(**d) for d in docs]
        except Exception as ex:
            logger.error("Failed to list dead letters: %s", ex)
            return []

    async def resolve_dead_letter(
        self,
        dead_letter_id: str,
        action: str,  # RETRIED, CANCELLED, RESOLVED_MANUALLY
        resolved_by: str,
        notes: Optional[str] = None,
    ) -> Optional[DeadLetterRecord]:
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            db = db_core.get_database()
            update_data = {
                "resolved": True,
                "resolved_by": resolved_by,
                "resolved_at": now_iso,
                "resolution_action": action,
                "resolution_notes": notes,
            }
            res = await db.notification_dead_letters.find_one_and_update(
                {"dead_letter_id": dead_letter_id},
                {"$set": update_data},
                return_document=True,
            )
            if res:
                return DeadLetterRecord(**res)
        except Exception as ex:
            logger.error("Failed to resolve dead letter %s: %s", dead_letter_id, ex)
        return None

    async def get_stats(self) -> Dict[str, Any]:
        try:
            db = db_core.get_database()
            total = await db.notification_dead_letters.count_documents({})
            unresolved = await db.notification_dead_letters.count_documents({"resolved": False})
            return {"total_dlq": total, "unresolved_dlq": unresolved}
        except Exception:
            return {"total_dlq": 0, "unresolved_dlq": 0}


dlq_service = DeadLetterQueueService()
