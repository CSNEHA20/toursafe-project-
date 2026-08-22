"""
TourSafe Incident Operational & Multi-Party Messaging Service

Coordinates mission-critical, secure, authenticated, and attributed operational chat
between Authority operators, Responders, and Tourists for specific incidents.
Provides strictly ordered monotonic server sequencing, message idempotency,
delivery/read/acknowledgement state tracking, audit logging, rate limiting, and realtime events.
"""

from datetime import datetime, timezone
import html
import logging
import time
from typing import Any, Dict, List, Optional
import uuid

from ...core import database as db_core
from ...schemas.emergency import (
    AttachmentMetadataRecord,
    AttachmentUploadRequest,
    AttachmentUploadResponse,
    ChannelParticipantRecord,
    ChannelSnapshotResponse,
    ChannelStatus,
    IncidentChannelRecord,
    IncidentMessageRecord,
    MessageAcknowledgementRecord,
    MessageDeliveryStatus,
    MessageGapRecoveryResponse,
    MessagePriority,
    MessageSearchResponse,
    MessageSendRequest,
    MessageType,
    ParticipantRole,
    ParticipantStatus,
    StructuredLocationData,
)
from ...schemas.realtime import RealtimeEventEnvelope, RealtimeEventType
from ...services.realtime_bus import realtime_bus
from .incident_channel_service import incident_channel_service
from .notifications import notification_service


def get_database():
    return db_core.get_database()


logger = logging.getLogger("toursafe.emergency.messaging")

# In-memory sliding window rate limiter: user_id -> list of timestamps
_RATE_LIMIT_STORE: Dict[str, List[float]] = {}
MAX_MESSAGES_PER_WINDOW = 30
RATE_LIMIT_WINDOW_SECONDS = 60


def check_rate_limit(user_id: str) -> bool:
    """Returns True if within rate limit, False if rate limit exceeded."""
    now = time.time()
    history = _RATE_LIMIT_STORE.setdefault(user_id, [])
    # Filter timestamps within window
    _RATE_LIMIT_STORE[user_id] = [t for t in history if now - t < RATE_LIMIT_WINDOW_SECONDS]
    if len(_RATE_LIMIT_STORE[user_id]) >= MAX_MESSAGES_PER_WINDOW:
        return False
    _RATE_LIMIT_STORE[user_id].append(now)
    return True


class MessagingService:
    """
    Manages incident operational and multi-party messages.
    """

    async def send_message(
        self,
        incident_id: str,
        sender_id: str,
        sender_role: Optional[Union[ParticipantRole, str]] = None,
        sender_name: Optional[str] = None,
        req: Any = None,
        sender_type: Optional[str] = None,
    ) -> IncidentMessageRecord:
        """
        Sends an attributed message to the incident channel.
        Guarantees:
        1. Channel status check (cannot post to CLOSED channel)
        2. Idempotency on client_message_id
        3. HTML sanitization and payload validation
        4. Rate limiting per sender
        5. Monotonic sequence numbering per channel
        6. Delivery tracking & Realtime broadcast
        7. Audit logging
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Resolve role / type
        resolved_role_str = str(sender_role or sender_type or "SYSTEM").upper()
        try:
            resolved_role = ParticipantRole(resolved_role_str)
        except Exception:
            resolved_role = ParticipantRole.SYSTEM

        # Resolve request model
        if req is None:
            raise ValueError("Message request cannot be None")
        if not isinstance(req, MessageSendRequest):
            content_val = getattr(req, "content", "")
            req = MessageSendRequest(
                content=content_val,
                client_message_id=getattr(req, "client_message_id", None),
                priority=getattr(req, "priority", MessagePriority.NORMAL),
                message_type=getattr(req, "message_type", MessageType.TEXT),
            )

        # 1. Rate limiting check
        if not check_rate_limit(sender_id):
            raise ValueError("Rate limit exceeded. Please wait before sending more messages.")

        # 2. Get or create channel and verify status
        channel = await incident_channel_service.get_or_create_channel(incident_id)
        if channel.status == ChannelStatus.CLOSED:
            raise ValueError(f"Incident channel '{incident_id}' is CLOSED. New operational messages are rejected.")

        # 3. Idempotency Check
        if req.client_message_id:
            existing_msg = await db.incident_messages.find_one({
                "incident_id": incident_id,
                "client_message_id": req.client_message_id,
            })
            if existing_msg:
                logger.info("Idempotent hit for client_message_id=%s in incident=%s", req.client_message_id, incident_id)
                return IncidentMessageRecord(**existing_msg)

        # 4. Content sanitization
        clean_content = html.escape(req.content.strip())
        if not clean_content:
            raise ValueError("Message content cannot be empty")

        # 5. Monotonic sequence allocation
        seq_update = await db.incident_channels.find_one_and_update(
            {"incident_id": incident_id},
            {"$inc": {"sequence_counter": 1}, "$set": {"updated_at": now_iso}},
            return_document=True,
        )
        server_sequence = seq_update.get("sequence_counter", 1) if seq_update else 1

        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        message = IncidentMessageRecord(
            message_id=message_id,
            channel_id=channel.channel_id,
            incident_id=incident_id,
            sender_id=sender_id,
            sender_role=resolved_role,
            sender_name=sender_name or "",
            message_type=req.message_type,
            priority=req.priority,
            content=clean_content,
            location_data=req.location_data,
            attachment_data=req.attachment_data,
            client_message_id=req.client_message_id,
            server_sequence=server_sequence,
            delivery_status=MessageDeliveryStatus.DELIVERED,
            requires_acknowledgement=req.requires_acknowledgement or (req.priority == MessagePriority.CRITICAL),
            read_by={sender_id: now_iso},
            acknowledged_by=[],
            created_at=now_iso,
            updated_at=now_iso,
        )

        # 6. Persist to MongoDB
        await db.incident_messages.insert_one(message.model_dump())

        # 7. Audit log record
        audit_entry = {
            "audit_id": f"aud_{uuid.uuid4().hex[:12]}",
            "action": "message.created",
            "incident_id": incident_id,
            "channel_id": channel.channel_id,
            "message_id": message_id,
            "server_sequence": server_sequence,
            "actor_id": sender_id,
            "actor_role": resolved_role.value,
            "priority": req.priority.value,
            "timestamp": now_iso,
        }
        await db.communication_audit_logs.insert_one(audit_entry)

        # 8. Realtime event publishing to incident channel
        await realtime_bus.publish_event(
            event_type=RealtimeEventType.MESSAGE_CREATED.value,
            payload=message.model_dump(),
            channel=f"incident:{incident_id}",
        )

        # 9. Deliver push / emergency notification if CRITICAL
        if req.priority == MessagePriority.CRITICAL:
            try:
                # Dispatch notification to authority / responders
                await notification_service.send_incident_notification(
                    incident_id=incident_id,
                    title=f"CRITICAL Incident Message - #{incident_id[-6:]}",
                    message=f"[{sender_role.value}] {clean_content[:120]}",
                    severity="CRITICAL",
                )
            except Exception as notif_err:
                logger.warning("Notification dispatch failed for critical message: %s", notif_err)

        return message

    async def send_system_message(
        self,
        incident_id: str,
        content: str,
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IncidentMessageRecord:
        """
        Generates an authoritative, non-editable system event message in the channel.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        channel = await incident_channel_service.get_or_create_channel(incident_id)

        seq_update = await db.incident_channels.find_one_and_update(
            {"incident_id": incident_id},
            {"$inc": {"sequence_counter": 1}, "$set": {"updated_at": now_iso}},
            return_document=True,
        )
        server_sequence = seq_update.get("sequence_counter", 1) if seq_update else 1

        message_id = f"sysmsg_{uuid.uuid4().hex[:12]}"
        message = IncidentMessageRecord(
            message_id=message_id,
            channel_id=channel.channel_id,
            incident_id=incident_id,
            sender_id="system",
            sender_role=ParticipantRole.SYSTEM,
            sender_name="System",
            message_type=MessageType.SYSTEM,
            priority=priority,
            content=content,
            server_sequence=server_sequence,
            delivery_status=MessageDeliveryStatus.DELIVERED,
            requires_acknowledgement=False,
            read_by={},
            acknowledged_by=[],
            created_at=now_iso,
            updated_at=now_iso,
        )

        await db.incident_messages.insert_one(message.model_dump())

        # Audit
        await db.communication_audit_logs.insert_one({
            "audit_id": f"aud_{uuid.uuid4().hex[:12]}",
            "action": "system_message.created",
            "incident_id": incident_id,
            "message_id": message_id,
            "server_sequence": server_sequence,
            "actor_id": "system",
            "actor_role": "SYSTEM",
            "timestamp": now_iso,
        })

        # Realtime event
        await realtime_bus.publish_event(
            event_type=RealtimeEventType.MESSAGE_CREATED.value,
            payload=message.model_dump(),
            channel=f"incident:{incident_id}",
        )
        return message

    async def acknowledge_message(
        self,
        incident_id: str,
        message_id: str,
        actor_id: str,
        actor_role: str,
        actor_name: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> IncidentMessageRecord:
        """
        Explicitly acknowledges a critical operational message.
        Read state is separate from Acknowledged state.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        doc = await db.incident_messages.find_one({
            "incident_id": incident_id,
            "message_id": message_id,
        })
        if not doc:
            raise ValueError(f"Message '{message_id}' not found in incident '{incident_id}'")

        # Check if already acknowledged by this actor
        existing_acks = doc.get("acknowledged_by", [])
        if any(ack.get("actor_id") == actor_id for ack in existing_acks):
            return IncidentMessageRecord(**doc)

        ack_record = MessageAcknowledgementRecord(
            actor_id=actor_id,
            actor_role=actor_role,
            actor_name=actor_name,
            acknowledged_at=now_iso,
            notes=notes,
        )

        await db.incident_messages.update_one(
            {"incident_id": incident_id, "message_id": message_id},
            {
                "$push": {"acknowledged_by": ack_record.model_dump()},
                "$set": {f"read_by.{actor_id}": now_iso, "updated_at": now_iso},
            },
        )

        updated_doc = await db.incident_messages.find_one({"incident_id": incident_id, "message_id": message_id})
        msg_record = IncidentMessageRecord(**updated_doc)

        # Audit
        await db.communication_audit_logs.insert_one({
            "audit_id": f"aud_{uuid.uuid4().hex[:12]}",
            "action": "message.acknowledged",
            "incident_id": incident_id,
            "message_id": message_id,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "timestamp": now_iso,
        })

        # Realtime event
        await realtime_bus.publish_event(
            event_type=RealtimeEventType.MESSAGE_ACKNOWLEDGED.value,
            payload={
                "incident_id": incident_id,
                "message_id": message_id,
                "acknowledgement": ack_record.model_dump(),
            },
            channel=f"incident:{incident_id}",
        )
        return msg_record

    async def mark_messages_read(
        self,
        incident_id: str,
        reader_id: str,
        up_to_sequence: Optional[int] = None,
    ) -> int:
        """
        Marks messages as read for a given reader up to the specified sequence.
        Updates reader participant's last_read_sequence and last_read_at.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        query: Dict[str, Any] = {"incident_id": incident_id}
        if up_to_sequence is not None:
            query["server_sequence"] = {"$lte": up_to_sequence}

        # Update messages
        res = await db.incident_messages.update_many(
            query,
            {"$set": {f"read_by.{reader_id}": now_iso}},
        )

        # Determine latest sequence read
        latest_read_seq = up_to_sequence
        if latest_read_seq is None:
            latest_msg = await db.incident_messages.find_one(
                {"incident_id": incident_id},
                sort=[("server_sequence", -1)],
            )
            latest_read_seq = latest_msg.get("server_sequence", 0) if latest_msg else 0

        # Update participant record
        await db.channel_participants.update_one(
            {"incident_id": incident_id, "user_id": reader_id},
            {"$set": {"last_read_sequence": latest_read_seq, "last_read_at": now_iso}},
        )

        # Realtime event
        await realtime_bus.publish_event(
            event_type=RealtimeEventType.MESSAGE_READ.value,
            payload={
                "incident_id": incident_id,
                "reader_id": reader_id,
                "last_read_sequence": latest_read_seq,
                "read_at": now_iso,
            },
            channel=f"incident:{incident_id}",
        )

        return res.modified_count

    async def get_messages(
        self,
        incident_id: str,
        limit: int = 50,
        skip: int = 0,
        since_sequence: Optional[int] = None,
    ) -> List[IncidentMessageRecord]:
        db = get_database()
        query: Dict[str, Any] = {"incident_id": incident_id, "deleted_at": None}
        if since_sequence is not None:
            query["server_sequence"] = {"$gt": since_sequence}

        cursor = db.incident_messages.find(query).sort("server_sequence", 1).skip(skip).limit(limit)
        items = []
        async for doc in cursor:
            items.append(IncidentMessageRecord(**doc))
        return items

    async def get_channel_snapshot(
        self,
        incident_id: str,
        user_id: str,
    ) -> ChannelSnapshotResponse:
        """
        Authoritative channel snapshot for reconnect and initial screen loading:
        Returns channel metadata, active participants, latest messages, sequence state, and unread counts.
        """
        db = get_database()
        channel = await incident_channel_service.get_or_create_channel(incident_id)
        participants = await incident_channel_service.get_participants(incident_id)

        # Find user's last read sequence
        user_participant = next((p for p in participants if p.user_id == user_id), None)
        last_read_seq = user_participant.last_read_sequence if user_participant else 0

        # Fetch recent 50 messages
        cursor = db.incident_messages.find({"incident_id": incident_id, "deleted_at": None}).sort("server_sequence", -1).limit(50)
        messages_desc = []
        async for doc in cursor:
            messages_desc.append(IncidentMessageRecord(**doc))
        messages = list(reversed(messages_desc))

        # Calculate unread count
        unread_count = await db.incident_messages.count_documents({
            "incident_id": incident_id,
            "deleted_at": None,
            "server_sequence": {"$gt": last_read_seq},
            "sender_id": {"$ne": user_id},
        })

        # Calculate pending acknowledgements count
        pending_acks = await db.incident_messages.count_documents({
            "incident_id": incident_id,
            "requires_acknowledgement": True,
            "acknowledged_by.actor_id": {"$ne": user_id},
            "sender_id": {"$ne": user_id},
        })

        return ChannelSnapshotResponse(
            channel=channel,
            participants=participants,
            messages=messages,
            last_sequence=channel.sequence_counter,
            unread_count=unread_count,
            pending_acknowledgements_count=pending_acks,
        )

    async def recover_gap(
        self,
        incident_id: str,
        since_sequence: int,
        limit: int = 100,
    ) -> MessageGapRecoveryResponse:
        """
        Recovers missing messages in a sequence gap (e.g. client received sequence 103 after 100).
        """
        db = get_database()
        channel = await incident_channel_service.get_or_create_channel(incident_id)
        cursor = db.incident_messages.find({
            "incident_id": incident_id,
            "server_sequence": {"$gt": since_sequence},
            "deleted_at": None,
        }).sort("server_sequence", 1).limit(limit)

        messages = []
        async for doc in cursor:
            messages.append(IncidentMessageRecord(**doc))

        return MessageGapRecoveryResponse(
            channel_id=channel.channel_id,
            incident_id=incident_id,
            since_sequence=since_sequence,
            current_sequence=channel.sequence_counter,
            messages=messages,
        )

    async def search_messages(
        self,
        incident_id: str,
        query: str,
        limit: int = 50,
    ) -> MessageSearchResponse:
        """
        Performs incident-scoped keyword search on messages.
        """
        db = get_database()
        clean_q = query.strip()
        if not clean_q:
            return MessageSearchResponse(incident_id=incident_id, query=query, total=0, messages=[])

        cursor = db.incident_messages.find({
            "incident_id": incident_id,
            "content": {"$regex": clean_q, "$options": "i"},
            "deleted_at": None,
        }).sort("server_sequence", -1).limit(limit)

        messages = []
        async for doc in cursor:
            messages.append(IncidentMessageRecord(**doc))

        return MessageSearchResponse(
            incident_id=incident_id,
            query=query,
            total=len(messages),
            messages=messages,
        )

    async def register_attachment(
        self,
        incident_id: str,
        uploader_id: str,
        req: AttachmentUploadRequest,
    ) -> AttachmentUploadResponse:
        """
        Registers an attachment metadata record for incident communication.
        Validates size and allowed MIME types.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Validation
        ALLOWED_MIME_TYPES = {
            "image/jpeg", "image/png", "image/webp", "image/heic",
            "application/pdf", "text/plain", "audio/mp4", "audio/mpeg"
        }
        if req.mime_type not in ALLOWED_MIME_TYPES:
            raise ValueError(f"MIME type '{req.mime_type}' is not supported for incident attachments")

        MAX_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
        if req.size_bytes > MAX_SIZE_BYTES:
            raise ValueError(f"Attachment size ({req.size_bytes} bytes) exceeds maximum allowable limit of 25MB")

        attachment_id = f"att_{uuid.uuid4().hex[:12]}"
        download_token = f"tok_{uuid.uuid4().hex[:16]}"
        url = f"/api/v1/incidents/{incident_id}/attachments/{attachment_id}"

        record = AttachmentMetadataRecord(
            attachment_id=attachment_id,
            file_name=req.file_name,
            mime_type=req.mime_type,
            size_bytes=req.size_bytes,
            url=url,
            sha256_hash=req.sha256_hash,
            is_formal_evidence=req.is_formal_evidence,
            uploaded_by=uploader_id,
            uploaded_at=now_iso,
        )

        doc = record.model_dump()
        doc["incident_id"] = incident_id
        doc["download_token"] = download_token
        await db.incident_attachments.insert_one(doc)

        return AttachmentUploadResponse(
            attachment=record,
            upload_url=f"/api/v1/incidents/{incident_id}/attachments/{attachment_id}/upload",
            download_token=download_token,
        )

    async def get_attachment(
        self,
        incident_id: str,
        attachment_id: str,
    ) -> Optional[AttachmentMetadataRecord]:
        db = get_database()
        doc = await db.incident_attachments.find_one({
            "incident_id": incident_id,
            "attachment_id": attachment_id,
        })
        if not doc:
            return None
        return AttachmentMetadataRecord(**doc)


messaging_service = MessagingService()
