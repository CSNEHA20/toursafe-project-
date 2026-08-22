from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from ...core import database as db_core
from ...schemas.notification import (
    CategoryPreference,
    DevicePlatform,
    DeviceRegisterRequest,
    DeviceTokenRecord,
    NotificationCategory,
    NotificationChannel,
    NotificationPayload,
    NotificationPriority,
    NotificationRecord,
    NotificationStatus,
    ProviderWebhookPayload,
    RecipientType,
    UserNotificationPreferences,
    UserPreferencesUpdateRequest,
)
from .policies.emergency_policy import emergency_policy
from .policies.policy_engine import policy_engine
from .providers.registry import provider_registry
from .queue.delivery_queue import delivery_queue
from .queue.dlq_service import dlq_service
from .resolver.recipient_resolver import recipient_resolver
from .templates.template_engine import template_engine

logger = logging.getLogger("toursafe.notifications.center")


class NotificationCenterService:
    """
    Central Orchestration Service for TourSafe Notifications & Communications.
    Connects domain events to policies, recipient resolvers, templates, queues, and providers.
    """

    def __init__(self):
        self.policy_engine = policy_engine
        self.emergency_policy = emergency_policy
        self.recipient_resolver = recipient_resolver
        self.template_engine = template_engine
        self.queue = delivery_queue
        self.dlq = dlq_service
        self.providers = provider_registry

    async def handle_domain_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        incident_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        tourist_id: Optional[str] = None,
        responder_id: Optional[str] = None,
        unit_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> List[NotificationRecord]:
        """
        Main entry point for domain events (e.g. incident.created, sos.triggered, etc.).
        Evaluates policies, resolves recipients, renders templates, and enqueues deliveries.
        """
        event_id = payload.get("event_id", f"evt_{uuid.uuid4().hex[:12]}")
        policies = self.policy_engine.evaluate_event(event_type, context=payload)
        records: List[NotificationRecord] = []

        for policy in policies:
            # 1. Resolve recipients for this policy
            resolved_recipients = []
            for rec_type in policy.recipient_types:
                if rec_type == RecipientType.AUTHORITY:
                    auth_recs = await self.recipient_resolver.resolve_authority_recipients(
                        incident=payload.get("incident"),
                        zone_id=zone_id,
                        channels=policy.channels,
                        priority=policy.priority,
                        is_mandatory=policy.is_mandatory,
                    )
                    resolved_recipients.extend(auth_recs)
                elif rec_type == RecipientType.RESPONDER:
                    resp_recs = await self.recipient_resolver.resolve_responder_recipients(
                        responder_id=responder_id or payload.get("responder_id"),
                        unit_id=unit_id or payload.get("unit_id"),
                        channels=policy.channels,
                        priority=policy.priority,
                        is_mandatory=policy.is_mandatory,
                    )
                    resolved_recipients.extend(resp_recs)
                elif rec_type == RecipientType.TOURIST:
                    t_id = tourist_id or payload.get("tourist_id")
                    if t_id:
                        tour_recs = await self.recipient_resolver.resolve_tourist_recipients(
                            tourist_id=t_id,
                            channels=policy.channels,
                            priority=policy.priority,
                            is_mandatory=policy.is_mandatory,
                        )
                        resolved_recipients.extend(tour_recs)
                elif rec_type == RecipientType.EMERGENCY_CONTACT:
                    t_id = tourist_id or payload.get("tourist_id")
                    if t_id:
                        contact_recs = await self.recipient_resolver.resolve_emergency_contacts(
                            tourist_id=t_id,
                            channels=policy.channels,
                        )
                        resolved_recipients.extend(contact_recs)

            # 2. Render templates and create notification records per recipient channel
            for recipient in resolved_recipients:
                for channel in recipient.channels:
                    # Template variables
                    tmpl_vars = {
                        "incident_id": incident_id or payload.get("incident_id", "N/A"),
                        "severity": payload.get("severity", "MEDIUM"),
                        "zone_name": payload.get("zone_name", "Assigned Zone"),
                        "reason": payload.get("reason", "Safety notification"),
                        "tourist_name": payload.get("tourist_name", "Tourist"),
                        "safety_state": payload.get("safety_state", "NORMAL"),
                        "risk_level": payload.get("risk_level", "NORMAL"),
                        "resolution_reason": payload.get("resolution_reason", "Completed"),
                        "title": payload.get("title", f"Alert: {event_type}"),
                        "message": payload.get("message", "A safety event occurred"),
                    }
                    tmpl_vars.update(payload)

                    title, body = self.template_engine.render(
                        template_id=policy.template_id,
                        variables=tmpl_vars,
                        locale=recipient.locale,
                        channel=channel,
                    )

                    idempotency_key = self.queue.generate_idempotency_key(
                        event_id=event_id,
                        recipient_id=recipient.recipient_id,
                        channel=channel,
                        template_version="v1",
                    )

                    notif = NotificationRecord(
                        event_id=event_id,
                        recipient_id=recipient.recipient_id,
                        recipient_type=recipient.recipient_type,
                        recipient_target=recipient.target_address,
                        incident_id=incident_id,
                        channel=channel,
                        priority=policy.priority,
                        category=policy.category,
                        template_id=policy.template_id,
                        policy_version=self.policy_engine.version,
                        idempotency_key=idempotency_key,
                        correlation_id=correlation_id,
                        payload=NotificationPayload(
                            title=title,
                            body=body,
                            incident_id=incident_id,
                            zone_id=zone_id,
                            deep_link=f"/incidents/{incident_id}" if incident_id else None,
                            data=payload,
                        ),
                    )

                    # Enqueue delivery
                    saved_record = await self.queue.enqueue(notif)
                    records.append(saved_record)

        return records

    async def get_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        category: Optional[NotificationCategory] = None,
        priority: Optional[NotificationPriority] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[NotificationRecord]:
        """Fetch notifications for in-app notification center."""
        db = db_core.get_database()
        query: Dict[str, Any] = {
            "$or": [
                {"recipient_id": user_id},
                {"recipient_id": "authority_operations_channel"},
            ]
        }
        if unread_only:
            query["is_read"] = False
        if category:
            query["category"] = category.value
        if priority:
            query["priority"] = priority.value

        cursor = db.notifications.find(query).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [NotificationRecord(**d) for d in docs]

    async def get_unread_count(self, user_id: str) -> int:
        db = db_core.get_database()
        return await db.notifications.count_documents({
            "$or": [
                {"recipient_id": user_id},
                {"recipient_id": "authority_operations_channel"},
            ],
            "is_read": False,
        })

    async def mark_as_read(self, notification_id: str, user_id: str) -> Optional[NotificationRecord]:
        db = db_core.get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        res = await db.notifications.find_one_and_update(
            {
                "notification_id": notification_id,
                "$or": [
                    {"recipient_id": user_id},
                    {"recipient_id": "authority_operations_channel"},
                ]
            },
            {"$set": {"is_read": True, "read_at": now_iso}},
            return_document=True,
        )
        if res:
            return NotificationRecord(**res)
        return None

    async def mark_all_as_read(self, user_id: str) -> int:
        db = db_core.get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        res = await db.notifications.update_many(
            {
                "$or": [
                    {"recipient_id": user_id},
                    {"recipient_id": "authority_operations_channel"},
                ],
                "is_read": False,
            },
            {"$set": {"is_read": True, "read_at": now_iso}}
        )
        return res.modified_count

    async def register_device(self, user_id: str, req: DeviceRegisterRequest) -> DeviceTokenRecord:
        db = db_core.get_database()
        dev_id = req.device_id or f"dev_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        record = DeviceTokenRecord(
            device_id=dev_id,
            user_id=user_id,
            platform=req.platform,
            token=req.token,
            app_version=req.app_version,
            active=True,
            last_seen=now_iso,
            created_at=now_iso,
            updated_at=now_iso,
        )

        await db.device_tokens.update_one(
            {"token": req.token},
            {"$set": record.model_dump()},
            upsert=True,
        )
        return record

    async def remove_device(self, user_id: str, device_id: str) -> bool:
        db = db_core.get_database()
        res = await db.device_tokens.delete_one({"device_id": device_id, "user_id": user_id})
        return res.deleted_count > 0

    async def get_user_devices(self, user_id: str) -> List[DeviceTokenRecord]:
        db = db_core.get_database()
        cursor = db.device_tokens.find({"user_id": user_id, "active": True})
        docs = await cursor.to_list(length=10)
        return [DeviceTokenRecord(**d) for d in docs]

    async def update_preferences(self, user_id: str, req: UserPreferencesUpdateRequest, role: str = "tourist") -> UserNotificationPreferences:
        db = db_core.get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        existing = await self.recipient_resolver.get_user_preferences(user_id, default_role=role)

        data = existing.model_dump()
        for k, v in req.model_dump(exclude_unset=True).items():
            if v is not None:
                data[k] = v
        data["updated_at"] = now_iso

        await db.notification_preferences.update_one(
            {"user_id": user_id},
            {"$set": data},
            upsert=True,
        )
        return UserNotificationPreferences(**data)

    async def process_provider_webhook(self, webhook: ProviderWebhookPayload) -> Dict[str, Any]:
        """
        Secure delivery status webhook handler.
        Verifies idempotency on provider_event_id and updates SENT -> DELIVERED / FAILED.
        """
        db = db_core.get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Idempotency check on provider event
        existing_event = await db.provider_webhook_events.find_one({"provider_event_id": webhook.provider_event_id})
        if existing_event:
            return {"status": "SKIPPED", "detail": "Provider webhook event already processed"}

        await db.provider_webhook_events.insert_one(webhook.model_dump())

        # 2. Update matching notification record
        query = {}
        if webhook.notification_id:
            query["notification_id"] = webhook.notification_id
        elif webhook.provider_message_id:
            query["provider_message_id"] = webhook.provider_message_id

        if not query:
            return {"status": "IGNORED", "detail": "No notification_id or provider_message_id provided"}

        status_map = {
            "delivered": NotificationStatus.DELIVERED,
            "failed": NotificationStatus.FAILED,
            "bounced": NotificationStatus.FAILED,
            "sent": NotificationStatus.SENT,
        }
        new_status = status_map.get(webhook.status.lower(), NotificationStatus.UNKNOWN)

        update_fields: Dict[str, Any] = {"status": new_status}
        if new_status == NotificationStatus.DELIVERED:
            update_fields["delivered_at"] = now_iso
        elif new_status == NotificationStatus.FAILED:
            update_fields["failed_at"] = now_iso
            update_fields["error_code"] = webhook.error_code or "WEBHOOK_REPORTED_FAILURE"
            update_fields["error_message"] = webhook.error_message

        res = await db.notifications.update_one(query, {"$set": update_fields})
        return {
            "status": "PROCESSED",
            "matched_count": res.matched_count,
            "modified_count": res.modified_count,
            "notification_status": new_status.value,
        }

    async def get_metrics(self) -> Dict[str, Any]:
        """Aggregate notification delivery observability metrics."""
        db = db_core.get_database()
        try:
            total = await db.notifications.count_documents({})
            delivered = await db.notifications.count_documents({"status": NotificationStatus.DELIVERED})
            sent = await db.notifications.count_documents({"status": NotificationStatus.SENT})
            failed = await db.notifications.count_documents({"status": NotificationStatus.FAILED})
            queued = await db.notifications.count_documents({"status": NotificationStatus.QUEUED})
            dlq_stats = await self.dlq.get_stats()
            return {
                "total_notifications": total,
                "delivered": delivered,
                "sent": sent,
                "failed": failed,
                "queued": queued,
                "dead_letters": dlq_stats.get("unresolved_dlq", 0),
            }
        except Exception:
            return {
                "total_notifications": 0,
                "delivered": 0,
                "sent": 0,
                "failed": 0,
                "queued": 0,
                "dead_letters": 0,
            }


notification_center = NotificationCenterService()
