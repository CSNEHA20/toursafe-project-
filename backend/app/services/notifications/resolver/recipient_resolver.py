from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from ....core import database as db_core
from ....schemas.notification import (
    NotificationChannel,
    NotificationPriority,
    RecipientType,
    UserNotificationPreferences,
)

logger = logging.getLogger("toursafe.notifications.resolver")


@dataclass
class ResolvedRecipient:
    recipient_id: str
    recipient_type: RecipientType
    channels: List[NotificationChannel]
    target_address: Optional[str] = None  # Phone, email, or device token
    locale: str = "en"
    user_role: str = "tourist"
    metadata: Dict[str, Any] = field(default_factory=dict)


class RecipientResolver:
    """
    Recipient Resolver for TourSafe.
    Resolves authorized destination users, respects quiet hours & preferences (with mandatory overrides),
    and prevents cross-organization/cross-role information leakage.
    """

    def __init__(self):
        pass

    async def get_user_preferences(self, user_id: str, default_role: str = "tourist") -> UserNotificationPreferences:
        try:
            db = db_core.get_database()
            pref_doc = await db.notification_preferences.find_one({"user_id": user_id})
            if pref_doc:
                return UserNotificationPreferences(**pref_doc)
        except Exception as ex:
            logger.warning("Failed to fetch preferences for user %s: %s", user_id, ex)

        # Default fallback preferences
        return UserNotificationPreferences(user_id=user_id, user_role=default_role)

    def is_in_quiet_hours(self, prefs: UserNotificationPreferences, now: Optional[datetime] = None) -> bool:
        if not prefs.quiet_hours_enabled or not prefs.quiet_hours_start or not prefs.quiet_hours_end:
            return False

        current_time = (now or datetime.now(timezone.utc)).strftime("%H:%M")
        start = prefs.quiet_hours_start
        end = prefs.quiet_hours_end

        if start <= end:
            return start <= current_time <= end
        else:
            # Spans midnight (e.g., 22:00 to 07:00)
            return current_time >= start or current_time <= end

    def filter_channels_by_preferences(
        self,
        requested_channels: List[NotificationChannel],
        prefs: UserNotificationPreferences,
        priority: NotificationPriority,
        is_mandatory: bool,
    ) -> List[NotificationChannel]:
        """
        Filter channels against user preferences.
        MANDATORY rules: If priority is CRITICAL or is_mandatory is True, quiet hours do NOT suppress!
        """
        if is_mandatory or priority == NotificationPriority.CRITICAL:
            return requested_channels

        # If in quiet hours for non-mandatory notification, suppress all external channels
        if self.is_in_quiet_hours(prefs):
            return [NotificationChannel.IN_APP]  # Leave in-app for silent review

        allowed = []
        for ch in requested_channels:
            if ch == NotificationChannel.IN_APP and prefs.in_app_enabled:
                allowed.append(ch)
            elif ch == NotificationChannel.REALTIME and prefs.realtime_enabled:
                allowed.append(ch)
            elif ch == NotificationChannel.PUSH and prefs.push_enabled:
                allowed.append(ch)
            elif ch == NotificationChannel.EMAIL and prefs.email_enabled:
                allowed.append(ch)
            elif ch == NotificationChannel.SMS and prefs.sms_enabled:
                allowed.append(ch)
            elif ch == NotificationChannel.VOICE and prefs.voice_enabled:
                allowed.append(ch)

        return allowed or [NotificationChannel.IN_APP]

    async def resolve_authority_recipients(
        self,
        incident: Optional[Dict[str, Any]] = None,
        zone_id: Optional[str] = None,
        channels: Optional[List[NotificationChannel]] = None,
        priority: NotificationPriority = NotificationPriority.HIGH,
        is_mandatory: bool = True,
    ) -> List[ResolvedRecipient]:
        """
        Resolve authority users within the relevant organization / region.
        """
        recipients: List[ResolvedRecipient] = []
        db = db_core.get_database()
        req_channels = channels or [NotificationChannel.REALTIME, NotificationChannel.IN_APP]

        query: Dict[str, Any] = {"role": "authority"}
        if incident and incident.get("organization_id"):
            query["organization_id"] = incident["organization_id"]

        try:
            cursor = db.users.find(query).limit(20)
            async for user_doc in cursor:
                uid = str(user_doc.get("id") or user_doc.get("_id"))
                prefs = await self.get_user_preferences(uid, default_role="authority")
                active_channels = self.filter_channels_by_preferences(req_channels, prefs, priority, is_mandatory)

                recipients.append(
                    ResolvedRecipient(
                        recipient_id=uid,
                        recipient_type=RecipientType.AUTHORITY,
                        channels=active_channels,
                        target_address=user_doc.get("email"),
                        user_role="authority",
                        metadata={"name": user_doc.get("name", "Authority Operator")},
                    )
                )
        except Exception as ex:
            logger.error("Failed to resolve authority recipients: %s", ex)

        # Fallback broadcast recipient if no individual authority accounts queried
        if not recipients:
            recipients.append(
                ResolvedRecipient(
                    recipient_id="authority_operations_channel",
                    recipient_type=RecipientType.AUTHORITY,
                    channels=req_channels,
                    user_role="authority",
                    metadata={"channel_override": "authority:operations", "role_target": "authority"},
                )
            )

        return recipients

    async def resolve_responder_recipients(
        self,
        responder_id: Optional[str] = None,
        unit_id: Optional[str] = None,
        channels: Optional[List[NotificationChannel]] = None,
        priority: NotificationPriority = NotificationPriority.CRITICAL,
        is_mandatory: bool = True,
    ) -> List[ResolvedRecipient]:
        """
        Resolve assigned responder or unit members.
        """
        recipients: List[ResolvedRecipient] = []
        db = db_core.get_database()
        req_channels = channels or [NotificationChannel.REALTIME, NotificationChannel.IN_APP, NotificationChannel.PUSH]

        try:
            if responder_id:
                resp_doc = await db.responders.find_one({"$or": [{"responder_id": responder_id}, {"id": responder_id}]})
                if resp_doc:
                    user_id = resp_doc.get("user_id") or responder_id
                    prefs = await self.get_user_preferences(user_id, default_role="responder")
                    active_channels = self.filter_channels_by_preferences(req_channels, prefs, priority, is_mandatory)
                    recipients.append(
                        ResolvedRecipient(
                            recipient_id=user_id,
                            recipient_type=RecipientType.RESPONDER,
                            channels=active_channels,
                            target_address=resp_doc.get("contact_phone"),
                            user_role="responder",
                            metadata={"responder_id": responder_id, "name": resp_doc.get("name")},
                        )
                    )
            elif unit_id:
                unit_doc = await db.responder_units.find_one({"$or": [{"unit_id": unit_id}, {"id": unit_id}]})
                if unit_doc and unit_doc.get("members"):
                    for mem_id in unit_doc["members"]:
                        sub_rec = await self.resolve_responder_recipients(responder_id=mem_id, channels=channels, priority=priority, is_mandatory=is_mandatory)
                        recipients.extend(sub_rec)
        except Exception as ex:
            logger.error("Failed to resolve responder recipients: %s", ex)

        return recipients

    async def resolve_tourist_recipients(
        self,
        tourist_id: str,
        channels: Optional[List[NotificationChannel]] = None,
        priority: NotificationPriority = NotificationPriority.HIGH,
        is_mandatory: bool = True,
    ) -> List[ResolvedRecipient]:
        """
        Resolve tourist recipient.
        """
        recipients: List[ResolvedRecipient] = []
        db = db_core.get_database()
        req_channels = channels or [NotificationChannel.REALTIME, NotificationChannel.IN_APP]

        try:
            tourist_doc = await db.tourists.find_one({"$or": [{"id": tourist_id}, {"user_id": tourist_id}]})
            user_id = tourist_doc.get("user_id", tourist_id) if tourist_doc else tourist_id
            prefs = await self.get_user_preferences(user_id, default_role="tourist")
            active_channels = self.filter_channels_by_preferences(req_channels, prefs, priority, is_mandatory)

            recipients.append(
                ResolvedRecipient(
                    recipient_id=user_id,
                    recipient_type=RecipientType.TOURIST,
                    channels=active_channels,
                    target_address=tourist_doc.get("phone") if tourist_doc else None,
                    user_role="tourist",
                    locale=tourist_doc.get("preferred_language", "en") if tourist_doc else "en",
                    metadata={"tourist_id": tourist_id, "channel_override": f"tourist:{tourist_id}"},
                )
            )
        except Exception as ex:
            logger.error("Failed to resolve tourist recipient %s: %s", tourist_id, ex)

        return recipients

    async def resolve_emergency_contacts(
        self,
        tourist_id: str,
        channels: Optional[List[NotificationChannel]] = None,
    ) -> List[ResolvedRecipient]:
        """
        Resolve authorized emergency contacts for a tourist.
        """
        recipients: List[ResolvedRecipient] = []
        db = db_core.get_database()
        req_channels = channels or [NotificationChannel.SMS, NotificationChannel.EMAIL]

        try:
            contacts_cursor = db.emergency_contacts.find({"tourist_id": tourist_id}).limit(5)
            contacts = await contacts_cursor.to_list(length=5)

            if not contacts:
                tourist_doc = await db.tourists.find_one({"$or": [{"id": tourist_id}, {"user_id": tourist_id}]})
                if tourist_doc and tourist_doc.get("emergency_contacts"):
                    contacts = tourist_doc["emergency_contacts"]
                elif tourist_doc and tourist_doc.get("emergency_contact_phone"):
                    contacts = [{
                        "name": tourist_doc.get("emergency_contact_name", "Emergency Contact"),
                        "phone": tourist_doc.get("emergency_contact_phone"),
                        "relationship": tourist_doc.get("emergency_contact_relation", "Contact"),
                    }]

            for c in contacts:
                phone = c.get("phone") or c.get("phone_e164") or c.get("contact_number")
                email = c.get("email")
                c_name = c.get("name", "Emergency Contact")

                if phone:
                    recipients.append(
                        ResolvedRecipient(
                            recipient_id=f"contact_{phone}",
                            recipient_type=RecipientType.EMERGENCY_CONTACT,
                            channels=[NotificationChannel.SMS],
                            target_address=phone,
                            user_role="emergency_contact",
                            metadata={"name": c_name, "relationship": c.get("relationship", "Contact")},
                        )
                    )
                if email:
                    recipients.append(
                        ResolvedRecipient(
                            recipient_id=f"contact_{email}",
                            recipient_type=RecipientType.EMERGENCY_CONTACT,
                            channels=[NotificationChannel.EMAIL],
                            target_address=email,
                            user_role="emergency_contact",
                            metadata={"name": c_name},
                        )
                    )
        except Exception as ex:
            logger.error("Failed to resolve emergency contacts for tourist %s: %s", tourist_id, ex)

        return recipients


recipient_resolver = RecipientResolver()
