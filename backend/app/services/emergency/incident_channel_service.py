"""
TourSafe Incident Channel Service

Manages incident-scoped communication channels, participant authorization,
role-based permissions, presence updates, and channel lifecycle transitions (ACTIVE, RESTRICTED, CLOSED).
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from ...core import database as db_core
from ...schemas.emergency import (
    ChannelParticipantAddRequest,
    ChannelParticipantRecord,
    ChannelParticipantUpdateRequest,
    ChannelStatus,
    IncidentChannelRecord,
    ParticipantPresenceStatus,
    ParticipantRole,
    ParticipantStatus,
    ResponderAssignmentRole,
)
from ...schemas.realtime import RealtimeEventEnvelope, RealtimeEventType
from ...services.realtime_bus import realtime_bus


def get_database():
    return db_core.get_database()


logger = logging.getLogger("toursafe.emergency.channel_service")


class IncidentChannelService:
    """
    Service responsible for incident communication channels and participant memberships.
    """

    async def get_or_create_channel(self, incident_id: str) -> IncidentChannelRecord:
        """
        Retrieves existing channel for an incident or initializes a new channel.
        Auto-populates the reporting tourist as an active participant.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        doc = await db.incident_channels.find_one({"incident_id": incident_id})
        if doc:
            return IncidentChannelRecord(**doc)

        # Verify incident exists
        incident_doc = await db.incidents.find_one({"incident_id": incident_id})
        if not incident_doc:
            raise ValueError(f"Incident '{incident_id}' not found")

        channel_id = f"chn_{uuid.uuid4().hex[:12]}"
        channel = IncidentChannelRecord(
            channel_id=channel_id,
            incident_id=incident_id,
            status=ChannelStatus.ACTIVE,
            sequence_counter=0,
            version=1,
            created_at=now_iso,
            updated_at=now_iso,
        )

        await db.incident_channels.insert_one(channel.model_dump())

        # Auto-add the tourist if present on the incident
        tourist_id = incident_doc.get("tourist_id")
        if tourist_id:
            tourist_doc = await db.tourist_profiles.find_one({"id": tourist_id})
            tourist_name = tourist_doc.get("full_name") if tourist_doc else "Tourist"
            tourist_user_id = tourist_doc.get("user_id") if tourist_doc else tourist_id

            tourist_participant = ChannelParticipantRecord(
                channel_id=channel_id,
                incident_id=incident_id,
                user_id=tourist_user_id,
                display_name=tourist_name,
                role=ParticipantRole.TOURIST,
                responder_role=ResponderAssignmentRole.NONE,
                status=ParticipantStatus.ACTIVE,
                permissions=["SEND_MESSAGE", "SEND_LOCATION", "ACKNOWLEDGE_MESSAGES"],
            )
            await db.channel_participants.insert_one(tourist_participant.model_dump())

        # Publish channel created event
        await realtime_bus.publish_event(
            event_type=RealtimeEventType.CHANNEL_UPDATED.value,
            payload={"channel_id": channel_id, "incident_id": incident_id, "status": "ACTIVE"},
            channel=f"incident:{incident_id}",
        )

        return channel

    async def get_channel(self, incident_id: str) -> Optional[IncidentChannelRecord]:
        db = get_database()
        doc = await db.incident_channels.find_one({"incident_id": incident_id})
        if not doc:
            return None
        return IncidentChannelRecord(**doc)

    async def add_participant(
        self,
        incident_id: str,
        user_id: str,
        display_name: str,
        role: ParticipantRole,
        responder_role: ResponderAssignmentRole = ResponderAssignmentRole.NONE,
        permissions: Optional[List[str]] = None,
    ) -> ChannelParticipantRecord:
        """
        Adds or reactivates a participant in the incident channel.
        """
        db = get_database()
        channel = await self.get_or_create_channel(incident_id)
        now_iso = datetime.now(timezone.utc).isoformat()

        if channel.status == ChannelStatus.CLOSED:
            raise ValueError("Cannot add participants to a CLOSED incident channel")

        default_perms = [
            "SEND_MESSAGE",
            "SEND_OPERATIONAL",
            "SEND_LOCATION",
            "SEND_ATTACHMENT",
            "ACKNOWLEDGE_MESSAGES",
        ]
        if role == ParticipantRole.TOURIST:
            default_perms = ["SEND_MESSAGE", "SEND_LOCATION", "ACKNOWLEDGE_MESSAGES"]
        elif role in (ParticipantRole.AUTHORITY, ParticipantRole.SUPERVISOR):
            default_perms.extend(["MANAGE_PARTICIPANTS", "VIEW_STAFF_NOTES", "CLOSE_CHANNEL"])

        resolved_permissions = permissions if permissions is not None else default_perms

        # Check existing participant
        existing = await db.channel_participants.find_one({
            "incident_id": incident_id,
            "user_id": user_id,
        })

        if existing:
            # Reactivate or update
            await db.channel_participants.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "status": ParticipantStatus.ACTIVE.value,
                        "display_name": display_name,
                        "role": role.value,
                        "responder_role": responder_role.value,
                        "permissions": resolved_permissions,
                        "left_at": None,
                    }
                },
            )
            updated = await db.channel_participants.find_one({"_id": existing["_id"]})
            record = ChannelParticipantRecord(**updated)
        else:
            record = ChannelParticipantRecord(
                channel_id=channel.channel_id,
                incident_id=incident_id,
                user_id=user_id,
                display_name=display_name,
                role=role,
                responder_role=responder_role,
                status=ParticipantStatus.ACTIVE,
                permissions=resolved_permissions,
                joined_at=now_iso,
            )
            await db.channel_participants.insert_one(record.model_dump())

        # Realtime event
        await realtime_bus.publish_event(
            event_type=RealtimeEventType.PARTICIPANT_ADDED.value,
            payload=record.model_dump(),
            channel=f"incident:{incident_id}",
        )

        return record

    async def update_participant(
        self,
        incident_id: str,
        user_id: str,
        req: ChannelParticipantUpdateRequest,
    ) -> ChannelParticipantRecord:
        db = get_database()
        existing = await db.channel_participants.find_one({
            "incident_id": incident_id,
            "user_id": user_id,
        })
        if not existing:
            raise ValueError(f"Participant with user_id '{user_id}' not found in incident '{incident_id}'")

        update_fields: Dict[str, Any] = {}
        if req.status is not None:
            update_fields["status"] = req.status.value
            if req.status == ParticipantStatus.REMOVED:
                update_fields["left_at"] = datetime.now(timezone.utc).isoformat()
        if req.responder_role is not None:
            update_fields["responder_role"] = req.responder_role.value
        if req.permissions is not None:
            update_fields["permissions"] = req.permissions

        if update_fields:
            await db.channel_participants.update_one(
                {"_id": existing["_id"]},
                {"$set": update_fields},
            )

        updated_doc = await db.channel_participants.find_one({"_id": existing["_id"]})
        record = ChannelParticipantRecord(**updated_doc)

        await realtime_bus.publish_event(
            event_type=RealtimeEventType.PARTICIPANT_UPDATED.value,
            payload=record.model_dump(),
            channel=f"incident:{incident_id}",
        )
        return record

    async def remove_participant(
        self,
        incident_id: str,
        user_id: str,
        reason: Optional[str] = None,
    ) -> ChannelParticipantRecord:
        return await self.update_participant(
            incident_id=incident_id,
            user_id=user_id,
            req=ChannelParticipantUpdateRequest(status=ParticipantStatus.REMOVED),
        )

    async def get_participants(
        self,
        incident_id: str,
        include_removed: bool = False,
    ) -> List[ChannelParticipantRecord]:
        db = get_database()
        query: Dict[str, Any] = {"incident_id": incident_id}
        if not include_removed:
            query["status"] = {"$ne": ParticipantStatus.REMOVED.value}

        cursor = db.channel_participants.find(query).sort("joined_at", 1)
        items = []
        async for doc in cursor:
            items.append(ChannelParticipantRecord(**doc))
        return items

    async def get_participant(
        self,
        incident_id: str,
        user_id: str,
    ) -> Optional[ChannelParticipantRecord]:
        db = get_database()
        doc = await db.channel_participants.find_one({
            "incident_id": incident_id,
            "user_id": user_id,
        })
        if not doc:
            return None
        return ChannelParticipantRecord(**doc)

    async def update_presence(
        self,
        incident_id: str,
        user_id: str,
        presence: ParticipantPresenceStatus,
    ) -> Optional[ChannelParticipantRecord]:
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        res = await db.channel_participants.update_one(
            {"incident_id": incident_id, "user_id": user_id},
            {"$set": {"presence": presence.value, "last_seen_at": now_iso}},
        )
        if res.matched_count == 0:
            return None

        updated_doc = await db.channel_participants.find_one({
            "incident_id": incident_id,
            "user_id": user_id,
        })
        record = ChannelParticipantRecord(**updated_doc)

        await realtime_bus.publish_event(
            event_type=RealtimeEventType.PARTICIPANT_PRESENCE.value,
            payload={
                "incident_id": incident_id,
                "user_id": user_id,
                "presence": presence.value,
                "last_seen_at": now_iso,
            },
            channel=f"incident:{incident_id}",
        )
        return record

    async def close_channel(self, incident_id: str) -> IncidentChannelRecord:
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        channel = await self.get_or_create_channel(incident_id)
        await db.incident_channels.update_one(
            {"incident_id": incident_id},
            {"$set": {"status": ChannelStatus.CLOSED.value, "closed_at": now_iso, "updated_at": now_iso}},
        )

        updated_doc = await db.incident_channels.find_one({"incident_id": incident_id})
        record = IncidentChannelRecord(**updated_doc)

        await realtime_bus.publish_event(
            event_type=RealtimeEventType.CHANNEL_UPDATED.value,
            payload={"incident_id": incident_id, "status": ChannelStatus.CLOSED.value, "closed_at": now_iso},
            channel=f"incident:{incident_id}",
        )
        return record

    async def reopen_channel(self, incident_id: str) -> IncidentChannelRecord:
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        channel = await self.get_or_create_channel(incident_id)
        await db.incident_channels.update_one(
            {"incident_id": incident_id},
            {"$set": {"status": ChannelStatus.ACTIVE.value, "closed_at": None, "updated_at": now_iso}},
        )

        updated_doc = await db.incident_channels.find_one({"incident_id": incident_id})
        record = IncidentChannelRecord(**updated_doc)

        await realtime_bus.publish_event(
            event_type=RealtimeEventType.CHANNEL_UPDATED.value,
            payload={"incident_id": incident_id, "status": ChannelStatus.ACTIVE.value},
            channel=f"incident:{incident_id}",
        )
        return record

    async def can_user_access_channel(
        self,
        incident_id: str,
        user_id: str,
        role: str,
    ) -> bool:
        """
        Enforces strict RBAC and isolation rules:
        - Admin: full access
        - Authority: full access to organization incidents
        - Responder: must be an active participant or currently assigned
        - Tourist: must be the tourist associated with the incident
        """
        if role in ("admin", "authority", "supervisor"):
            return True

        db = get_database()
        # Check channel participants
        part = await db.channel_participants.find_one({
            "incident_id": incident_id,
            "user_id": user_id,
            "status": {"$ne": ParticipantStatus.REMOVED.value},
        })
        if part:
            return True

        # Check incident directly
        incident = await db.incidents.find_one({"incident_id": incident_id})
        if not incident:
            return False

        if role == "tourist":
            # Compare user_id with tourist profile or tourist_id
            t_profile = await db.tourist_profiles.find_one({"user_id": user_id})
            if t_profile and t_profile.get("id") == incident.get("tourist_id"):
                return True
            if incident.get("tourist_id") == user_id:
                return True

        elif role == "responder":
            resp = await db.responders.find_one({"user_id": user_id})
            resp_id = resp.get("responder_id") if resp else user_id
            # Check if active assignment exists for this responder and incident
            asgn = await db.incident_assignments.find_one({
                "incident_id": incident_id,
                "responder_id": resp_id,
                "status": {"$in": ["PENDING", "ACCEPTED", "ACTIVE"]},
            })
            if asgn:
                return True

        return False


incident_channel_service = IncidentChannelService()
