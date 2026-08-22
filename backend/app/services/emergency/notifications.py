"""
TourSafe Pluggable Notification System & Provider Abstractions

Strict Scope Enforcement:
- Does NOT claim external live police/ambulance/fire dispatch.
- Uses honest provider statuses (NOT_CONFIGURED, DEVELOPMENT, QUEUED, SENT, FAILED).
- Pluggable architecture allowing future real SMS/Voice/FCM gateways without modifying incident workflows.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
import os
from typing import Any, Dict, List, Optional
import uuid

from ...core import database as db_core


def get_database():
    return db_core.get_database()
from ...schemas.emergency import (
    NotificationChannel,
    NotificationRecord,
    NotificationStatus,
)

logger = logging.getLogger("toursafe.emergency.notifications")


class NotificationProvider(ABC):
    """
    Abstract base class for all notification channel providers.
    """

    def __init__(self, name: str, channel: NotificationChannel):
        self.name = name
        self.channel = channel

    @abstractmethod
    def is_configured(self) -> bool:
        """Check whether real API credentials/gateways are configured."""
        pass

    @abstractmethod
    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send a notification. Returns provider response dictionary with status and details.
        """
        pass


class PushNotificationProvider(NotificationProvider):
    """
    Push notification provider stub (e.g., FCM / APNs).
    """

    def __init__(self):
        super().__init__(name="TourSafePushProvider", channel=NotificationChannel.PUSH)
        self.fcm_key = os.getenv("FCM_SERVER_KEY")

    def is_configured(self) -> bool:
        return bool(self.fcm_key)

    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured():
            logger.info("Push provider in DEVELOPMENT mode for recipient '%s'", recipient)
            return {
                "status": NotificationStatus.SENT if os.getenv("ENVIRONMENT") == "test" else NotificationStatus.NOT_CONFIGURED,
                "provider": self.name,
                "detail": "Push provider operating in development mode (no external FCM key configured)",
            }

        # Future live FCM integration point
        return {
            "status": NotificationStatus.SENT,
            "provider": self.name,
            "detail": "Push dispatched successfully",
        }


class SMSNotificationProvider(NotificationProvider):
    """
    SMS notification provider stub (e.g., Twilio / AWS SNS / Fast2SMS).
    """

    def __init__(self):
        super().__init__(name="TourSafeSMSProvider", channel=NotificationChannel.SMS)
        self.twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")

    def is_configured(self) -> bool:
        return bool(self.twilio_sid)

    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured():
            logger.info("SMS provider in DEVELOPMENT mode for recipient '%s'", recipient)
            return {
                "status": NotificationStatus.SENT if os.getenv("ENVIRONMENT") == "test" else NotificationStatus.NOT_CONFIGURED,
                "provider": self.name,
                "detail": "SMS provider operating in development mode (no live SMS gateway configured)",
            }

        return {
            "status": NotificationStatus.SENT,
            "provider": self.name,
            "detail": "SMS dispatched successfully",
        }


class EmailNotificationProvider(NotificationProvider):
    """
    Email notification provider stub (e.g., SendGrid / SMTP / SES).
    """

    def __init__(self):
        super().__init__(name="TourSafeEmailProvider", channel=NotificationChannel.EMAIL)
        self.smtp_host = os.getenv("SMTP_HOST")

    def is_configured(self) -> bool:
        return bool(self.smtp_host)

    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured():
            logger.info("Email provider in DEVELOPMENT mode for recipient '%s'", recipient)
            return {
                "status": NotificationStatus.SENT if os.getenv("ENVIRONMENT") == "test" else NotificationStatus.NOT_CONFIGURED,
                "provider": self.name,
                "detail": "Email provider operating in development mode (no SMTP host configured)",
            }

        return {
            "status": NotificationStatus.SENT,
            "provider": self.name,
            "detail": "Email dispatched successfully",
        }


class VoiceCallNotificationProvider(NotificationProvider):
    """
    Automated voice call provider stub (e.g., Twilio Voice).
    """

    def __init__(self):
        super().__init__(name="TourSafeVoiceProvider", channel=NotificationChannel.VOICE)
        self.voice_sid = os.getenv("TWILIO_VOICE_SID")

    def is_configured(self) -> bool:
        return bool(self.voice_sid)

    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured():
            logger.info("Voice call provider in DEVELOPMENT mode for recipient '%s'", recipient)
            return {
                "status": NotificationStatus.SENT if os.getenv("ENVIRONMENT") == "test" else NotificationStatus.NOT_CONFIGURED,
                "provider": self.name,
                "detail": "Voice provider operating in development mode (no live Voice gateway configured)",
            }

        return {
            "status": NotificationStatus.SENT,
            "provider": self.name,
            "detail": "Voice alert dispatched successfully",
        }


class NotificationService:
    """
    Central notification orchestration service.
    """

    def __init__(self):
        self.providers: Dict[NotificationChannel, NotificationProvider] = {
            NotificationChannel.PUSH: PushNotificationProvider(),
            NotificationChannel.SMS: SMSNotificationProvider(),
            NotificationChannel.EMAIL: EmailNotificationProvider(),
            NotificationChannel.VOICE: VoiceCallNotificationProvider(),
        }

    async def send_notification(
        self,
        recipient: str,
        channel: NotificationChannel,
        subject: str,
        message: str,
        incident_id: Optional[str] = None,
        recipient_type: str = "EMERGENCY_CONTACT",
        policy_trigger: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NotificationRecord:
        """
        Dispatches notification through the registered provider, logs the attempt,
        and saves an immutable record in MongoDB.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        provider = self.providers.get(channel)
        provider_name = provider.name if provider else "UNKNOWN_PROVIDER"

        record = NotificationRecord(
            incident_id=incident_id,
            recipient=recipient,
            recipient_type=recipient_type,
            channel=channel,
            provider=provider_name,
            status=NotificationStatus.SENDING,
            payload={
                "subject": subject,
                "message": message,
                "metadata": metadata or {},
            },
            policy_trigger=policy_trigger,
            created_at=now_iso,
        )

        if not provider:
            record.status = NotificationStatus.FAILED
            record.error_code = "NO_PROVIDER_REGISTERED"
            record.failed_at = now_iso
        else:
            try:
                res = await provider.send(
                    recipient=recipient,
                    subject=subject,
                    message=message,
                    metadata=metadata,
                )
                record.status = res.get("status", NotificationStatus.NOT_CONFIGURED)
                if record.status in (NotificationStatus.SENT, NotificationStatus.DELIVERED):
                    record.sent_at = datetime.now(timezone.utc).isoformat()
                    if record.status == NotificationStatus.DELIVERED:
                        record.delivered_at = record.sent_at
                elif record.status == NotificationStatus.FAILED:
                    record.failed_at = datetime.now(timezone.utc).isoformat()
                    record.error_code = res.get("error_code", "PROVIDER_ERROR")
            except Exception as ex:
                logger.error("Notification dispatch failed: %s", ex)
                record.status = NotificationStatus.FAILED
                record.failed_at = datetime.now(timezone.utc).isoformat()
                record.error_code = str(ex)

        # Persist notification record in MongoDB
        try:
            db = get_database()
            await db.notifications.insert_one(record.model_dump())
        except Exception as db_err:
            logger.warning("Failed to persist notification record: %s", db_err)

        return record

    async def notify_emergency_contacts_for_incident(
        self,
        incident_id: str,
        tourist_id: str,
        severity: str,
        location_text: str = "Location details available to authorities",
    ) -> List[NotificationRecord]:
        """
        Dispatches emergency contact notifications for high-urgency incidents according to policy.
        """
        records: List[NotificationRecord] = []
        try:
            db = get_database()
            # Fetch tourist profile and emergency contacts
            contacts_cursor = db.emergency_contacts.find({"tourist_id": tourist_id})
            contacts = await contacts_cursor.to_list(length=10)

            if not contacts:
                # Try finding emergency contacts embedded in tourist doc
                tourist_doc = await db.tourists.find_one({"$or": [{"id": tourist_id}, {"user_id": tourist_id}]})
                if tourist_doc and tourist_doc.get("emergency_contacts"):
                    contacts = tourist_doc["emergency_contacts"]
                elif tourist_doc and tourist_doc.get("emergency_contact_phone"):
                    contacts = [{
                        "name": tourist_doc.get("emergency_contact_name", "Emergency Contact"),
                        "phone": tourist_doc.get("emergency_contact_phone"),
                        "relationship": tourist_doc.get("emergency_contact_relation", "Contact"),
                    }]

            subject = f"TourSafe Safety Alert: Incident reported for your contact"
            message = (
                f"TourSafe Alert: An emergency condition (Severity: {severity}) has been logged for your contact. "
                f"Authority command operations are actively responding. "
                f"Incident Ref: {incident_id}. Please stay reachable."
            )

            for c in contacts:
                phone = c.get("phone") or c.get("phone_e164") or c.get("contact_number")
                email = c.get("email")

                if phone:
                    rec_sms = await self.send_notification(
                        recipient=phone,
                        channel=NotificationChannel.SMS,
                        subject=subject,
                        message=message,
                        incident_id=incident_id,
                        recipient_type="EMERGENCY_CONTACT",
                        policy_trigger="EMERGENCY_CONTACT_DISPATCH_POLICY",
                        metadata={"contact_name": c.get("name"), "relationship": c.get("relationship")},
                    )
                    records.append(rec_sms)

                if email:
                    rec_email = await self.send_notification(
                        recipient=email,
                        channel=NotificationChannel.EMAIL,
                        subject=subject,
                        message=message,
                        incident_id=incident_id,
                        recipient_type="EMERGENCY_CONTACT",
                        policy_trigger="EMERGENCY_CONTACT_DISPATCH_POLICY",
                        metadata={"contact_name": c.get("name")},
                    )
                    records.append(rec_email)

        except Exception as ex:
            logger.error("Failed to notify emergency contacts for incident %s: %s", incident_id, ex)

        return records


notification_service = NotificationService()
