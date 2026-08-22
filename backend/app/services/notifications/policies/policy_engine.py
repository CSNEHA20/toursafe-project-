from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional

from ....schemas.notification import (
    NotificationCategory,
    NotificationChannel,
    NotificationPriority,
    RecipientType,
)

logger = logging.getLogger("toursafe.notifications.policies")


@dataclass
class ChannelPolicy:
    channels: List[NotificationChannel]
    priority: NotificationPriority
    category: NotificationCategory
    template_id: str
    recipient_types: List[RecipientType]
    fallback_channels: List[NotificationChannel] = field(default_factory=list)
    ttl_seconds: Optional[int] = None
    is_mandatory: bool = False  # If true, user preferences/quiet hours CANNOT suppress


class NotificationPolicyEngine:
    """
    Policy Engine for TourSafe notifications.
    Translates canonical domain events (e.g. 'incident.created', 'sos.triggered')
    into concrete channel dispatches, priorities, template selections, and fallbacks.
    """

    def __init__(self, version: str = "notification-policy-v1"):
        self.version = version
        self._policies: Dict[str, List[ChannelPolicy]] = {}
        self._initialize_policies()

    def _initialize_policies(self):
        # 1. incident.created (or sos.triggered)
        self._policies["incident.created"] = [
            # For Authorities
            ChannelPolicy(
                channels=[NotificationChannel.REALTIME, NotificationChannel.IN_APP, NotificationChannel.PUSH],
                priority=NotificationPriority.CRITICAL,
                category=NotificationCategory.INCIDENT,
                template_id="incident-created-authority",
                recipient_types=[RecipientType.AUTHORITY],
                fallback_channels=[NotificationChannel.SMS],
                is_mandatory=True,
            ),
            # For Tourist
            ChannelPolicy(
                channels=[NotificationChannel.REALTIME, NotificationChannel.IN_APP],
                priority=NotificationPriority.CRITICAL,
                category=NotificationCategory.SOS,
                template_id="sos-acknowledged-tourist",
                recipient_types=[RecipientType.TOURIST],
                is_mandatory=True,
            ),
        ]

        # 2. incident.acknowledged
        self._policies["incident.acknowledged"] = [
            ChannelPolicy(
                channels=[NotificationChannel.REALTIME, NotificationChannel.IN_APP],
                priority=NotificationPriority.HIGH,
                category=NotificationCategory.INCIDENT,
                template_id="sos-acknowledged-tourist",
                recipient_types=[RecipientType.TOURIST],
                is_mandatory=True,
            ),
        ]

        # 3. incident.assigned
        self._policies["incident.assigned"] = [
            ChannelPolicy(
                channels=[NotificationChannel.REALTIME, NotificationChannel.IN_APP, NotificationChannel.PUSH],
                priority=NotificationPriority.CRITICAL,
                category=NotificationCategory.ASSIGNMENT,
                template_id="incident-assigned-responder",
                recipient_types=[RecipientType.RESPONDER],
                fallback_channels=[NotificationChannel.SMS],
                is_mandatory=True,
            ),
            ChannelPolicy(
                channels=[NotificationChannel.REALTIME, NotificationChannel.IN_APP],
                priority=NotificationPriority.HIGH,
                category=NotificationCategory.INCIDENT,
                template_id="system-alert",
                recipient_types=[RecipientType.AUTHORITY, RecipientType.TOURIST],
                is_mandatory=False,
            ),
        ]

        # 4. incident.escalated
        self._policies["incident.escalated"] = [
            ChannelPolicy(
                channels=[NotificationChannel.REALTIME, NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.SMS],
                priority=NotificationPriority.CRITICAL,
                category=NotificationCategory.INCIDENT,
                template_id="incident-escalated-authority",
                recipient_types=[RecipientType.AUTHORITY],
                is_mandatory=True,
            ),
        ]

        # 5. incident.resolved
        self._policies["incident.resolved"] = [
            ChannelPolicy(
                channels=[NotificationChannel.REALTIME, NotificationChannel.IN_APP],
                priority=NotificationPriority.HIGH,
                category=NotificationCategory.INCIDENT,
                template_id="incident-resolved-tourist",
                recipient_types=[RecipientType.TOURIST],
                is_mandatory=True,
            ),
            ChannelPolicy(
                channels=[NotificationChannel.REALTIME, NotificationChannel.IN_APP],
                priority=NotificationPriority.NORMAL,
                category=NotificationCategory.ASSIGNMENT,
                template_id="incident-resolved-responder",
                recipient_types=[RecipientType.RESPONDER],
                is_mandatory=False,
            ),
            ChannelPolicy(
                channels=[NotificationChannel.REALTIME, NotificationChannel.IN_APP],
                priority=NotificationPriority.NORMAL,
                category=NotificationCategory.INCIDENT,
                template_id="system-alert",
                recipient_types=[RecipientType.AUTHORITY],
                is_mandatory=False,
            ),
        ]

        # 6. emergency_contact.alert
        self._policies["emergency_contact.alert"] = [
            ChannelPolicy(
                channels=[NotificationChannel.SMS, NotificationChannel.EMAIL],
                priority=NotificationPriority.CRITICAL,
                category=NotificationCategory.SAFETY,
                template_id="emergency-contact-alert",
                recipient_types=[RecipientType.EMERGENCY_CONTACT],
                is_mandatory=True,
            ),
        ]

        # 7. zone.warning
        self._policies["zone.warning"] = [
            ChannelPolicy(
                channels=[NotificationChannel.REALTIME, NotificationChannel.IN_APP, NotificationChannel.PUSH],
                priority=NotificationPriority.HIGH,
                category=NotificationCategory.ZONE,
                template_id="zone-warning-tourist",
                recipient_types=[RecipientType.TOURIST],
                is_mandatory=False,
            ),
        ]

        # 8. safety.state_changed
        self._policies["safety.state_changed"] = [
            ChannelPolicy(
                channels=[NotificationChannel.REALTIME, NotificationChannel.IN_APP],
                priority=NotificationPriority.NORMAL,
                category=NotificationCategory.SAFETY,
                template_id="safety-state-changed",
                recipient_types=[RecipientType.TOURIST],
                is_mandatory=False,
            ),
        ]

        # 9. system.alert
        self._policies["system.alert"] = [
            ChannelPolicy(
                channels=[NotificationChannel.IN_APP],
                priority=NotificationPriority.LOW,
                category=NotificationCategory.SYSTEM,
                template_id="system-alert",
                recipient_types=[RecipientType.TOURIST, RecipientType.AUTHORITY, RecipientType.RESPONDER],
                is_mandatory=False,
            ),
        ]

    def evaluate_event(
        self,
        event_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[ChannelPolicy]:
        """
        Evaluate domain event and return applicable channel policies.
        """
        policies = self._policies.get(event_type, [])
        if not policies:
            # Default fallback policy for custom or unknown domain events
            return [
                ChannelPolicy(
                    channels=[NotificationChannel.IN_APP],
                    priority=NotificationPriority.NORMAL,
                    category=NotificationCategory.SYSTEM,
                    template_id="system-alert",
                    recipient_types=[RecipientType.TOURIST, RecipientType.AUTHORITY],
                    is_mandatory=False,
                )
            ]
        return policies


policy_engine = NotificationPolicyEngine()
