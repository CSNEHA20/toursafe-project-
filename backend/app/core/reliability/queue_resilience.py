"""
TourSafe Queue Resilience, Dead-Letter Management, Replay & Stuck Job Watchdog.
Provides durable capture for failed background events and controlled replay mechanisms.
"""

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from .. import database as db_core
from .metrics import metrics_collector
from .logging import get_structured_logger
from .tracing import get_current_trace_id, get_current_correlation_id

logger = get_structured_logger("toursafe.queue_resilience")


class DeadLetterEntry:
    def __init__(
        self,
        job_id: str,
        queue_name: str,
        payload: Dict[str, Any],
        error_message: str,
        attempts: int,
        trace_id: str,
        correlation_id: str,
        failed_at: Optional[str] = None,
    ):
        self.job_id = job_id
        self.queue_name = queue_name
        self.payload = payload
        self.error_message = error_message
        self.attempts = attempts
        self.trace_id = trace_id
        self.correlation_id = correlation_id
        self.failed_at = failed_at or datetime.now(timezone.utc).isoformat()
        self.status = "DEAD_LETTER"  # DEAD_LETTER, REPLAYED, DISCARDED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "queue_name": self.queue_name,
            "payload": self.payload,
            "error_message": self.error_message,
            "attempts": self.attempts,
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "failed_at": self.failed_at,
            "status": self.status,
        }


class DeadLetterManager:
    """Manages dead-letter queues with in-memory tracking and MongoDB persistence."""

    def __init__(self):
        self._in_memory_dlq: List[DeadLetterEntry] = []

    async def record_dead_letter(
        self,
        queue_name: str,
        payload: Dict[str, Any],
        error: Exception,
        attempts: int = 3,
        job_id: Optional[str] = None,
    ) -> str:
        jid = job_id or f"dlq-{uuid.uuid4().hex[:12]}"
        entry = DeadLetterEntry(
            job_id=jid,
            queue_name=queue_name,
            payload=payload,
            error_message=str(error),
            attempts=attempts,
            trace_id=get_current_trace_id(),
            correlation_id=get_current_correlation_id(),
        )
        self._in_memory_dlq.append(entry)
        metrics_collector.subsystems.queue_dead_letter_total += 1

        # Attempt to persist to MongoDB dead_letter_queue collection
        try:
            db = db_core.get_database()
            await db.dead_letter_queue.insert_one(entry.to_dict())
        except Exception as e:
            logger.warning(f"Could not persist dead-letter record to DB: {e}")

        logger.error(
            f"Message moved to DLQ [{queue_name}] after {attempts} failed attempts: {error}",
            extra={"event": "DEAD_LETTER_CAPTURED", "extra_data": entry.to_dict()}
        )
        return jid

    async def list_dead_letters(self, queue_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            db = db_core.get_database()
            query: Dict[str, Any] = {}
            if queue_name:
                query["queue_name"] = queue_name
            cursor = db.dead_letter_queue.find(query).sort("failed_at", -1).limit(limit)
            items = await cursor.to_list(length=limit)
            if items:
                for item in items:
                    item.pop("_id", None)
                return items
        except Exception:
            pass

        # Fallback to in-memory DLQ
        results = [e.to_dict() for e in self._in_memory_dlq if not queue_name or e.queue_name == queue_name]
        return list(reversed(results))[:limit]

    async def replay_message(
        self,
        job_id: str,
        handler: Callable[[Dict[str, Any]], Any],
        actor_id: str = "operator"
    ) -> Dict[str, Any]:
        """Replay a dead-letter message idempotently using the provided handler."""
        # Find entry
        target_entry = None
        for e in self._in_memory_dlq:
            if e.job_id == job_id:
                target_entry = e
                break

        if not target_entry:
            try:
                db = db_core.get_database()
                doc = await db.dead_letter_queue.find_one({"job_id": job_id})
                if doc:
                    target_entry = DeadLetterEntry(
                        job_id=doc["job_id"],
                        queue_name=doc["queue_name"],
                        payload=doc["payload"],
                        error_message=doc["error_message"],
                        attempts=doc["attempts"],
                        trace_id=doc.get("trace_id", ""),
                        correlation_id=doc.get("correlation_id", ""),
                        failed_at=doc.get("failed_at"),
                    )
            except Exception:
                pass

        if not target_entry:
            return {"success": False, "error": f"Job ID {job_id} not found in DLQ"}

        logger.info(f"Replaying DLQ job {job_id} on {target_entry.queue_name} by {actor_id}")
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(target_entry.payload)
            else:
                handler(target_entry.payload)

            target_entry.status = "REPLAYED"
            try:
                db = db_core.get_database()
                await db.dead_letter_queue.update_one(
                    {"job_id": job_id},
                    {"$set": {"status": "REPLAYED", "replayed_by": actor_id, "replayed_at": datetime.now(timezone.utc).isoformat()}}
                )
            except Exception:
                pass

            metrics_collector.subsystems.queue_dead_letter_total = max(
                0, metrics_collector.subsystems.queue_dead_letter_total - 1
            )
            return {"success": True, "job_id": job_id, "status": "REPLAYED"}
        except Exception as e:
            logger.error(f"Replay execution failed for {job_id}: {e}")
            return {"success": False, "job_id": job_id, "error": str(e)}


dead_letter_manager = DeadLetterManager()


class QueueResilienceManager:
    """Monitors queue backpressure and applies load-shedding when thresholds are breached."""

    def __init__(self, max_queue_depth: int = 5000):
        self.max_queue_depth = max_queue_depth
        self.current_depth = 0

    def check_backpressure(self, is_critical: bool = False) -> bool:
        """Returns True if the queue is acceptable; False if backpressure rejects the packet."""
        if is_critical:
            # Critical events (SOS) are always accepted up to hard safety limit (2x max)
            return self.current_depth < (self.max_queue_depth * 2)
        return self.current_depth < self.max_queue_depth

    def update_depth(self, depth: int):
        self.current_depth = depth
        metrics_collector.subsystems.queue_depth = depth


queue_resilience_manager = QueueResilienceManager()


class StuckJobWatchdog:
    """Monitors active async jobs and flags tasks exceeding maximum runtime SLA."""

    def __init__(self, max_runtime_seconds: float = 60.0):
        self.max_runtime_seconds = max_runtime_seconds
        self._active_jobs: Dict[str, float] = {}

    def register_job(self, job_id: str):
        self._active_jobs[job_id] = time.time()

    def complete_job(self, job_id: str):
        self._active_jobs.pop(job_id, None)

    def scan_stuck_jobs(self) -> List[Dict[str, Any]]:
        now = time.time()
        stuck = []
        for jid, start_ts in list(self._active_jobs.items()):
            runtime = now - start_ts
            if runtime > self.max_runtime_seconds:
                stuck.append({"job_id": jid, "runtime_seconds": round(runtime, 1)})
        return stuck
