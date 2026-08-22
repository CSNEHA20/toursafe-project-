import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NotificationChannel(str, Enum):
    IN_APP = "IN_APP"
    REALTIME = "REALTIME"
    PUSH = "PUSH"
    SMS = "SMS"
    EMAIL = "EMAIL"
    VOICE = "VOICE"


class NotificationPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class NotificationCategory(str, Enum):
    SAFETY = "SAFETY"
    INCIDENT = "INCIDENT"
    SOS = "SOS"
    ZONE = "ZONE"
    RESPONDER = "RESPONDER"
    ASSIGNMENT = "ASSIGNMENT"
    SYSTEM = "SYSTEM"
    ACCOUNT = "ACCOUNT"


class NotificationStatus(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNKNOWN = "UNKNOWN"


class DeliveryErrorCategory(str, Enum):
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    RATE_LIMITED = "RATE_LIMITED"
    AUTH_FAILURE = "AUTH_FAILURE"
    INVALID_RECIPIENT = "INVALID_RECIPIENT"
    UNKNOWN = "UNKNOWN"


class RecipientType(str, Enum):
    TOURIST = "TOURIST"
    AUTHORITY = "AUTHORITY"
    RESPONDER = "RESPONDER"
    EMERGENCY_CONTACT = "EMERGENCY_CONTACT"
    SYSTEM = "SYSTEM"


class DevicePlatform(str, Enum):
    IOS = "IOS"
    ANDROID = "ANDROID"
    WEB = "WEB"


# ---------------------------------------------------------------------------
# Core Notification Record
# ---------------------------------------------------------------------------

class NotificationDeliveryAttempt(BaseModel):
    attempt_number: int
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    provider: str
    status: NotificationStatus
    error_category: Optional[DeliveryErrorCategory] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    provider_message_id: Optional[str] = None
    latency_ms: Optional[float] = None


class NotificationPayload(BaseModel):
    title: str
    body: str
    data: Dict[str, Any] = Field(default_factory=dict)
    action_url: Optional[str] = None
    incident_id: Optional[str] = None
    zone_id: Optional[str] = None
    assignment_id: Optional[str] = None
    deep_link: Optional[str] = None


class NotificationRecord(BaseModel):
    notification_id: str = Field(default_factory=lambda: f"notif_{uuid.uuid4().hex[:12]}")
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    recipient_id: str
    recipient_type: RecipientType = RecipientType.TOURIST
    recipient_target: Optional[str] = None  # Phone, email, device token, or user_id
    incident_id: Optional[str] = None
    channel: NotificationChannel = NotificationChannel.IN_APP
    priority: NotificationPriority = NotificationPriority.NORMAL
    category: NotificationCategory = NotificationCategory.SYSTEM
    template_id: Optional[str] = None
    template_version: str = "v1"
    policy_version: str = "notification-policy-v1"
    idempotency_key: str
    correlation_id: Optional[str] = None

    status: NotificationStatus = NotificationStatus.CREATED
    payload: NotificationPayload

    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    scheduled_at: Optional[str] = None
    sent_at: Optional[str] = None
    delivered_at: Optional[str] = None
    failed_at: Optional[str] = None
    expires_at: Optional[str] = None

    provider: str = "UNASSIGNED"
    provider_message_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    is_read: bool = False
    read_at: Optional[str] = None

    delivery_history: List[NotificationDeliveryAttempt] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Dead Letter Queue Record
# ---------------------------------------------------------------------------

class DeadLetterRecord(BaseModel):
    dead_letter_id: str = Field(default_factory=lambda: f"dlq_{uuid.uuid4().hex[:12]}")
    notification_id: str
    event_id: str
    incident_id: Optional[str] = None
    recipient_id: str
    recipient_type: RecipientType
    channel: NotificationChannel
    provider: str
    attempts: int
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    last_error_category: Optional[DeliveryErrorCategory] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload_snapshot: Dict[str, Any] = Field(default_factory=dict)
    resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[str] = None
    resolution_action: Optional[str] = None  # RETRIED, CANCELLED, RESOLVED_MANUALLY
    resolution_notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Device Registration Record
# ---------------------------------------------------------------------------

class DeviceTokenRecord(BaseModel):
    device_id: str = Field(default_factory=lambda: f"dev_{uuid.uuid4().hex[:10]}")
    user_id: str
    platform: DevicePlatform = DevicePlatform.WEB
    token: str
    app_version: Optional[str] = "1.0.0"
    active: bool = True
    last_seen: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DeviceRegisterRequest(BaseModel):
    device_id: Optional[str] = None
    platform: DevicePlatform = DevicePlatform.WEB
    token: str
    app_version: Optional[str] = "1.0.0"


# ---------------------------------------------------------------------------
# User Notification Preferences
# ---------------------------------------------------------------------------

class CategoryPreference(BaseModel):
    in_app: bool = True
    realtime: bool = True
    push: bool = True
    email: bool = False
    sms: bool = False


class UserNotificationPreferences(BaseModel):
    user_id: str
    user_role: str = "tourist"  # tourist, authority, responder
    in_app_enabled: bool = True
    realtime_enabled: bool = True
    push_enabled: bool = True
    email_enabled: bool = True
    sms_enabled: bool = True
    voice_enabled: bool = False  # strictly optional opt-in

    quiet_hours_enabled: bool = False
    quiet_hours_start: Optional[str] = "22:00"  # HH:MM (UTC or local)
    quiet_hours_end: Optional[str] = "07:00"

    # Per-category overrides (Optional categories can be configured; Mandatory cannot be silenced)
    category_preferences: Dict[str, CategoryPreference] = Field(default_factory=dict)

    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class UserPreferencesUpdateRequest(BaseModel):
    in_app_enabled: Optional[bool] = None
    realtime_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    voice_enabled: Optional[bool] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    category_preferences: Optional[Dict[str, CategoryPreference]] = None


# ---------------------------------------------------------------------------
# Communication Audit Record
# ---------------------------------------------------------------------------

class CommunicationAuditRecord(BaseModel):
    audit_id: str = Field(default_factory=lambda: f"aud_{uuid.uuid4().hex[:12]}")
    event_id: str
    notification_id: str
    incident_id: Optional[str] = None
    actor_id: Optional[str] = None  # Who or what system event triggered it
    recipient_id: str
    recipient_type: RecipientType
    channel: NotificationChannel
    provider: str
    policy_version: str
    template_version: str
    delivery_status: NotificationStatus
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    retry_count: int = 0
    failure_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Template Models & Webhooks
# ---------------------------------------------------------------------------

class NotificationTemplateRecord(BaseModel):
    template_id: str
    version: str = "v1"
    locale: str = "en"
    title_template: str
    body_template: str
    channels: List[NotificationChannel]
    allowed_variables: List[str] = Field(default_factory=list)


class ProviderWebhookPayload(BaseModel):
    provider: str
    provider_event_id: str
    notification_id: Optional[str] = None
    provider_message_id: Optional[str] = None
    status: str  # e.g., "delivered", "failed", "bounced", "opened"
    timestamp: Optional[str] = None
    signature: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_payload: Dict[str, Any] = Field(default_factory=dict)


class ProviderHealthResponse(BaseModel):
    provider_name: str
    channel: NotificationChannel
    configured: bool
    status: str  # "AVAILABLE", "NOT_CONFIGURED", "DEGRADED", "UNAVAILABLE"
    detail: str
    last_health_check: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
