import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional
import uuid

from ...core.database import get_database
from ...schemas.integrations import DeadLetterRecord, IntegrationType
from .security import security_manager

logger = logging.getLogger("toursafe.integrations.dead_letter")


class DeadLetterQueueService:
    """
    Dead-Letter Queue (DLQ) Service.
    Stores unrecoverable or max-retry-exceeded integration tasks for inspection and authorized manual replay.
    """

    def __init__(self):
        self._memory_dlq: Dict[str, Dict[str, Any]] = {}

    async def enqueue(
        self,
        operation_name: str,
        integration_id: str,
        provider_name: str,
        integration_type: IntegrationType,
        idempotency_key: str,
        correlation_id: str,
        attempt_count: int,
        max_attempts: int,
        error_code: str,
        error_message: str,
        payload_summary: Optional[Dict[str, Any]] = None,
    ) -> DeadLetterRecord:
        record_id = f"dlq_{uuid.uuid4().hex[:12]}"
        sanitized_summary = security_manager.redact_secrets(payload_summary or {})

        record = DeadLetterRecord(
            record_id=record_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            operation_name=operation_name,
            integration_id=integration_id,
            provider_name=provider_name,
            integration_type=integration_type,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            attempt_count=attempt_count,
            max_attempts=max_attempts,
            error_code=error_code,
            error_message=error_message,
            payload_summary=sanitized_summary,
            resolved=False,
        )

        doc = record.model_dump() if hasattr(record, "model_dump") else record.dict()
        doc["_id"] = record_id

        # In-memory storage
        self._memory_dlq[record_id] = doc

        # MongoDB storage
        try:
            db = get_database()
            if db is not None:
                await asyncio.wait_for(db["integration_dead_letters"].insert_one(doc), timeout=0.5)
        except Exception as e:
            logger.debug("DeadLetterQueueService: MongoDB insertion notice: %s", e)

        logger.error(
            "DeadLetterQueue: ENQUEUED [%s] op=%s provider=%s error=%s attempts=%d/%d",
            record_id,
            operation_name,
            provider_name,
            error_code,
            attempt_count,
            max_attempts,
        )
        return record

    async def list_records(
        self,
        resolved: Optional[bool] = None,
        integration_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        try:
            db = get_database()
            if db is not None:
                query = {}
                if resolved is not None:
                    query["resolved"] = resolved
                if integration_id:
                    query["integration_id"] = integration_id
                cursor = db["integration_dead_letters"].find(query).sort("timestamp", -1).limit(limit)
                return await cursor.to_list(length=limit)
        except Exception as e:
            logger.warning("DeadLetterQueueService: MongoDB query fallback: %s", e)

        records = list(self._memory_dlq.values())
        if resolved is not None:
            records = [r for r in records if r.get("resolved") == resolved]
        if integration_id:
            records = [r for r in records if r.get("integration_id") == integration_id]
        records.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return records[:limit]

    async def get_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        try:
            db = get_database()
            if db is not None:
                doc = await db["integration_dead_letters"].find_one({"record_id": record_id})
                if doc:
                    return doc
        except Exception as e:
            logger.warning("DeadLetterQueueService: DB query record error: %s", e)
        return self._memory_dlq.get(record_id)

    async def mark_resolved(self, record_id: str, actor_id: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        if record_id in self._memory_dlq:
            self._memory_dlq[record_id]["resolved"] = True
            self._memory_dlq[record_id]["resolved_at"] = now
            self._memory_dlq[record_id]["resolved_by"] = actor_id

        try:
            db = get_database()
            if db is not None:
                await db["integration_dead_letters"].update_one(
                    {"record_id": record_id},
                    {"$set": {"resolved": True, "resolved_at": now, "resolved_by": actor_id}},
                )
                return True
        except Exception as e:
            logger.warning("DeadLetterQueueService: DB mark_resolved error: %s", e)
            return True
        return record_id in self._memory_dlq


# Global Singleton
dead_letter_service = DeadLetterQueueService()
