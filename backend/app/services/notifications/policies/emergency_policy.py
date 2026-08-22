from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from ....schemas.notification import (
    NotificationChannel,
    NotificationPriority,
    RecipientType,
)

logger = logging.getLogger("toursafe.notifications.policies.emergency")


@dataclass
class EmergencyStageConfig:
    stage_number: int
    name: str
    channels: List[NotificationChannel]
    recipient_types: List[RecipientType]
    min_severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    delay_seconds: int
    auto_trigger: bool = True
    requires_consent: bool = False


class EmergencyCommunicationPolicy:
    """
    Emergency Communication Multi-Stage Policy.
    Defines escalating response stages for critical safety & SOS events.
    """

    def __init__(self, policy_version: str = "emergency-policy-v1"):
        self.version = policy_version
        self.stages: List[EmergencyStageConfig] = [
            EmergencyStageConfig(
                stage_number=1,
                name="IMMEDIATE_AUTHORITY_REALTIME",
                channels=[NotificationChannel.REALTIME, NotificationChannel.IN_APP],
                recipient_types=[RecipientType.AUTHORITY, RecipientType.TOURIST],
                min_severity="LOW",
                delay_seconds=0,
                auto_trigger=True,
            ),
            EmergencyStageConfig(
                stage_number=2,
                name="RESPONDER_PUSH_DISPATCH",
                channels=[NotificationChannel.PUSH, NotificationChannel.REALTIME, NotificationChannel.IN_APP],
                recipient_types=[RecipientType.RESPONDER, RecipientType.AUTHORITY],
                min_severity="MEDIUM",
                delay_seconds=0,
                auto_trigger=True,
            ),
            EmergencyStageConfig(
                stage_number=3,
                name="EMERGENCY_CONTACT_SMS_EMAIL",
                channels=[NotificationChannel.SMS, NotificationChannel.EMAIL],
                recipient_types=[RecipientType.EMERGENCY_CONTACT],
                min_severity="HIGH",
                delay_seconds=30,  # Grace window allowing tourist or authority acknowledgement
                auto_trigger=True,
                requires_consent=True,
            ),
            EmergencyStageConfig(
                stage_number=4,
                name="HIGHER_AUTHORITY_ESCALATION",
                channels=[NotificationChannel.PUSH, NotificationChannel.SMS, NotificationChannel.REALTIME],
                recipient_types=[RecipientType.AUTHORITY],
                min_severity="CRITICAL",
                delay_seconds=120,
                auto_trigger=True,
            ),
            EmergencyStageConfig(
                stage_number=5,
                name="EXTERNAL_PROVIDER_DISPATCH_GATED",
                channels=[NotificationChannel.VOICE],
                recipient_types=[RecipientType.AUTHORITY],
                min_severity="CRITICAL",
                delay_seconds=300,
                auto_trigger=False,  # Strictly manual/gated by human supervisor
            ),
        ]

    def get_stages_for_severity(self, severity: str) -> List[EmergencyStageConfig]:
        sev_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        curr_rank = sev_rank.get(severity.upper(), 1)
        return [s for s in self.stages if sev_rank.get(s.min_severity.upper(), 1) <= curr_rank]


emergency_policy = EmergencyCommunicationPolicy()
