import asyncio
from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, List, Optional
import uuid

from ....core import database as db_core
from ....schemas.notification import (
    CommunicationAuditRecord,
    DeliveryErrorCategory,
    NotificationChannel,
    NotificationDeliveryAttempt,
    NotificationPriority,
    NotificationRecord,
    NotificationStatus,
)
from ..providers.base import ProviderDeliveryResult
from ..providers.registry import provider_registry
from .dlq_service import dlq_service
from .retry_engine import retry_engine

logger = logging.getLogger("toursafe.notifications.queue.delivery")


class DeliveryQueueService:
    """
    Durable Delivery Queue and Execution Engine.
    Handles deduplication via idempotency keys, durable state transitions in MongoDB,
    retry execution with exponential backoff, and DLQ escalation.
    """

    def __init__(self):
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    @staticmethod
    def generate_idempotency_key(
        event_id: str,
        recipient_id: str,
        channel: NotificationChannel,
        template_version: str = "v1",
    ) -> str:
        """Create SHA-256 idempotency signature for a notification target."""
        raw = f"{event_id}:{recipient_id}:{channel.value}:{template_version}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def enqueue(self, notification: NotificationRecord) -> NotificationRecord:
        """
        Durable enqueue. Checks idempotency to prevent duplicate dispatches for the same event.
        """
        db = db_core.get_database()

        # Check existing notification with identical idempotency key
        existing = await db.notifications.find_one({"idempotency_key": notification.idempotency_key})
        if existing:
            logger.info("Duplicate notification suppressed via idempotency_key: %s", notification.idempotency_key)
            return NotificationRecord(**existing)

        notification.status = NotificationStatus.QUEUED
        await db.notifications.insert_one(notification.model_dump())

        # Proactively execute delivery immediately
        return await self.process_notification(notification)

    async def process_notification(self, notification: NotificationRecord) -> NotificationRecord:
        """
        Process single notification delivery attempt.
        """
        db = db_core.get_database()
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        # Check expiration
        if notification.expires_at:
            try:
                exp_dt = datetime.fromisoformat(notification.expires_at)
                if now_dt >= exp_dt:
                    notification.status = NotificationStatus.EXPIRED
                    await db.notifications.update_one(
                        {"notification_id": notification.notification_id},
                        {"$set": {"status": NotificationStatus.EXPIRED}}
                    )
                    logger.info("Notification %s expired prior to dispatch", notification.notification_id)
                    return notification
            except Exception:
                pass

        provider = provider_registry.get_provider(notification.channel)
        if not provider:
            notification.status = NotificationStatus.FAILED
            notification.error_code = "NO_PROVIDER_FOR_CHANNEL"
            notification.error_message = f"No active provider adapter registered for channel {notification.channel.value}"
            notification.failed_at = now_iso
            await db.notifications.update_one(
                {"notification_id": notification.notification_id},
                {"$set": notification.model_dump()}
            )
            await dlq_service.enqueue_dead_letter(
                notification,
                reason="Unregistered provider",
                last_error_code=notification.error_code,
                last_error_message=notification.error_message,
                last_error_category=DeliveryErrorCategory.PERMANENT,
            )
            return notification

        notification.provider = provider.name
        notification.status = NotificationStatus.SENDING
        notification.retry_count += 1

        # Target recipient string: target_address or user_id or recipient_id
        target = notification.recipient_target or notification.recipient_id

        # Dispatch via provider
        start_time = datetime.now(timezone.utc)
        result: ProviderDeliveryResult = await provider.send(
            recipient=target,
            subject=notification.payload.title,
            body=notification.payload.body,
            metadata={
                "notification_id": notification.notification_id,
                "incident_id": notification.incident_id,
                "category": notification.category.value,
                "priority": notification.priority.value,
                "deep_link": notification.payload.deep_link,
                "data": notification.payload.data,
                "user_id": notification.recipient_id,
            },
            priority=notification.priority,
            idempotency_key=notification.idempotency_key,
        )
        end_time = datetime.now(timezone.utc)
        latency_ms = (end_time - start_time).total_seconds() * 1000.0

        # Record attempt history
        attempt = NotificationDeliveryAttempt(
            attempt_number=notification.retry_count,
            timestamp=now_iso,
            provider=result.provider_name,
            status=result.status,
            error_category=result.error_category,
            error_code=result.error_code,
            error_message=result.error_message,
            provider_message_id=result.provider_message_id,
            latency_ms=latency_ms,
        )
        notification.delivery_history.append(attempt)
        notification.provider_message_id = result.provider_message_id

        if result.status in (NotificationStatus.SENT, NotificationStatus.DELIVERED):
            notification.status = result.status
            notification.sent_at = now_iso
            if result.status == NotificationStatus.DELIVERED:
                notification.delivered_at = now_iso
        elif result.status == NotificationStatus.NOT_CONFIGURED:
            notification.status = NotificationStatus.NOT_CONFIGURED
            notification.error_code = result.error_code
            notification.error_message = result.error_message
        else:
            # Handle failure & retries
            notification.error_code = result.error_code
            notification.error_message = result.error_message

            if retry_engine.should_retry(notification.retry_count, result.error_category):
                notification.status = NotificationStatus.RETRYING
                delay = retry_engine.calculate_backoff_delay(notification.retry_count)
                logger.info(
                    "Notification %s scheduled for retry #%d in %.2fs [err=%s]",
                    notification.notification_id,
                    notification.retry_count + 1,
                    delay,
                    result.error_code,
                )
            else:
                notification.status = NotificationStatus.FAILED
                notification.failed_at = now_iso
                await dlq_service.enqueue_dead_letter(
                    notification,
                    reason=f"Delivery failed ({result.error_code or 'UNKNOWN'})",
                    last_error_code=result.error_code,
                    last_error_message=result.error_message,
                    last_error_category=result.error_category,
                )

        # Persist updated status
        await db.notifications.update_one(
            {"notification_id": notification.notification_id},
            {"$set": notification.model_dump()}
        )

        # Record communication audit entry
        await self._record_audit(notification)

        return notification

    async def _record_audit(self, notification: NotificationRecord):
        """Append communication audit record for compliance and tracing."""
        audit = CommunicationAuditRecord(
            event_id=notification.event_id,
            notification_id=notification.notification_id,
            incident_id=notification.incident_id,
            actor_id=notification.correlation_id or "system",
            recipient_id=notification.recipient_id,
            recipient_type=notification.recipient_type,
            channel=notification.channel,
            provider=notification.provider,
            policy_version=notification.policy_version,
            template_version=notification.template_version,
            delivery_status=notification.status,
            retry_count=notification.retry_count,
            failure_reason=notification.error_message,
            metadata={"priority": notification.priority.value, "category": notification.category.value},
        )
        try:
            db = db_core.get_database()
            await db.communication_audits.insert_one(audit.model_dump())
        except Exception as ex:
            logger.warning("Failed to record communication audit for %s: %s", notification.notification_id, ex)

    async def cancel_pending_notifications(self, incident_id: str, reason: str = "Incident state changed"):
        """Cancel all pending or queued notifications related to an incident."""
        try:
            db = db_core.get_database()
            res = await db.notifications.update_many(
                {
                    "incident_id": incident_id,
                    "status": {"$in": [NotificationStatus.QUEUED, NotificationStatus.RETRYING, NotificationStatus.CREATED]},
                },
                {
                    "$set": {
                        "status": NotificationStatus.CANCELLED,
                        "error_message": f"Cancelled: {reason}",
                    }
                }
            )
            logger.info("Cancelled %d pending notifications for incident %s", res.modified_count, incident_id)
        except Exception as ex:
            logger.error("Failed to cancel pending notifications for incident %s: %s", incident_id, ex)


delivery_queue = DeliveryQueueService()
