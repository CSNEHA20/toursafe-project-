# TourSafe Notification & Communication Architecture

This document describes the production-grade notification and communication infrastructure implemented in TourSafe (Prompt 14), separating domain event generation from multi-channel delivery.

---

## 1. Core Architecture & Event Flow

TourSafe strictly decouples domain event generation from notification delivery:

```
DOMAIN EVENT (e.g., incident.created, sos.triggered, incident.assigned)
      │
      ▼
EVENT BUS (realtime_bus / notification_center)
      │
      ▼
NOTIFICATION POLICY ENGINE (notification-policy-v1 / emergency_policy)
      │
      ▼
RECIPIENT RESOLVER (Role, Org, Responder Assignment, Emergency Contacts, Preferences)
      │
      ▼
CHANNEL SELECTION (IN_APP, REALTIME, PUSH, SMS, EMAIL, VOICE)
      │
      ▼
TEMPLATE ENGINE (Versioned, Multi-locale, Security-filtered)
      │
      ▼
DURABLE DELIVERY QUEUE & RETRY ENGINE (Redis / Mongo with Exponential Backoff + Jitter)
      │
      ▼
PROVIDER ADAPTERS (InApp, Realtime, Push, SMS, Email, Voice)
      │
      ├── Success ──► DELIVERY TRACKING & AUDIT TRAIL
      └── Failure (exhausted retries) ──► DEAD-LETTER QUEUE (DLQ)
```

---

## 2. Notification Domain Model

Every notification is represented as an immutable domain record with full lifecycle tracking:

- `notification_id`: Canonical unique identifier (`notif_...`)
- `event_id`: Originating domain event ID (`evt_...`)
- `recipient_id`: Target user, authority operator, responder, or contact
- `recipient_type`: `TOURIST`, `AUTHORITY`, `RESPONDER`, `EMERGENCY_CONTACT`, `SYSTEM`
- `incident_id`: Linked incident identifier (where applicable)
- `channel`: `IN_APP`, `REALTIME`, `PUSH`, `SMS`, `EMAIL`, `VOICE`
- `priority`: `LOW`, `NORMAL`, `HIGH`, `CRITICAL`
- `category`: `SAFETY`, `INCIDENT`, `SOS`, `ZONE`, `RESPONDER`, `ASSIGNMENT`, `SYSTEM`, `ACCOUNT`
- `template_id` & `template_version`: Versioned template tracking (`v1`)
- `policy_version`: Policy engine decision tracking (`notification-policy-v1`)
- `idempotency_key`: SHA-256 composite signature `(event_id:recipient_id:channel:template_version)`
- `status`: `CREATED`, `QUEUED`, `SENDING`, `SENT`, `DELIVERED`, `FAILED`, `RETRYING`, `CANCELLED`, `EXPIRED`, `NOT_CONFIGURED`, `UNKNOWN`
- `timestamps`: `created_at`, `scheduled_at`, `sent_at`, `delivered_at`, `failed_at`, `expires_at`
- `provider`: Resolved provider adapter name
- `provider_message_id`: Upstream carrier/gateway message reference
- `retry_count` & `max_retries`: Execution attempts counter
- `delivery_history`: Ordered log of delivery attempts with latency, error classification, and provider responses
- `is_read` & `read_at`: In-app read tracking

---

## 3. Provider Abstraction Layer

All channels implement the `NotificationProvider` interface:

```python
class NotificationProvider(ABC):
    def is_configured(self) -> bool: ...
    async def health_check(self) -> Dict[str, Any]: ...
    async def send(self, recipient, subject, body, metadata, priority, idempotency_key) -> ProviderDeliveryResult: ...
    async def get_status(self, provider_message_id) -> Optional[NotificationStatus]: ...
    async def cancel(self, provider_message_id) -> bool: ...
```

### Registered Provider Adapters:
1. **`InAppNotificationProvider`**: Persists records directly in MongoDB with unread tracking.
2. **`RealtimeNotificationProvider`**: Dispatches instant WebSocket notification envelopes over the `realtime_bus`.
3. **`PushNotificationProvider`**: FCM / APNs adapter with device token invalidation on `UNREGISTERED` errors.
4. **`SMSNotificationProvider`**: Twilio / AWS SNS / Fast2SMS adapter with E.164 phone verification.
5. **`EmailNotificationProvider`**: SMTP / SendGrid / Amazon SES adapter with RFC email verification.
6. **`VoiceCallNotificationProvider`**: Twilio Voice abstraction. Strictly gated by `ENABLE_LIVE_VOICE_CALLS=false` to prevent automated dial danger.

---

## 4. Honesty & No Fake Delivery

TourSafe strictly distinguishes:
- `NOT_CONFIGURED`: Missing provider API keys in environment.
- `DEV_PROVIDER`: Test environment mock provider logging actions without claiming external dispatch.
- `SENT`: Accepted by upstream carrier/relay.
- `DELIVERED`: Confirmed by delivery receipt webhook. `SENT != DELIVERED`.
- `FAILED`: Explicitly categorized error.

---

## 5. Notification Policy Engine (`notification-policy-v1`)

Maps canonical domain events to multi-channel distribution rules:

| Domain Event | Target Recipient Types | Channels | Priority | Mandatory |
| :--- | :--- | :--- | :--- | :--- |
| `incident.created` | Authority, Tourist | REALTIME, IN_APP, PUSH | CRITICAL | **Yes** |
| `incident.acknowledged` | Tourist | REALTIME, IN_APP | HIGH | **Yes** |
| `incident.assigned` | Responder, Tourist, Authority | REALTIME, IN_APP, PUSH, SMS fallback | CRITICAL | **Yes** |
| `incident.escalated` | Authority Command | REALTIME, IN_APP, PUSH, SMS | CRITICAL | **Yes** |
| `incident.resolved` | Tourist, Responder, Authority | REALTIME, IN_APP | HIGH | **Yes** |
| `emergency_contact.alert` | Emergency Contacts | SMS, EMAIL | CRITICAL | **Yes** |
| `zone.warning` | Tourist | REALTIME, IN_APP, PUSH | HIGH | No |
| `safety.state_changed` | Tourist | REALTIME, IN_APP | NORMAL | No |
| `system.alert` | All Roles | IN_APP | LOW / NORMAL | No |

---

## 6. Emergency Multi-Stage Policy

Defines escalating response stages for critical incidents:

- **Stage 1 (T+0s)**: Immediate Authority & Tourist Realtime WebSocket + In-App notification.
- **Stage 2 (T+0s)**: Responder Push & Realtime Tactical dispatch.
- **Stage 3 (T+30s)**: Emergency Contact SMS & Email alerts (allowing grace window for acknowledgement).
- **Stage 4 (T+120s)**: Higher Authority escalation notifications (SMS & Push).
- **Stage 5 (T+300s)**: External Provider voice dispatch (strictly gated by human supervisor).

---

## 7. Recipient Resolution & Safe Scoping

`RecipientResolver` resolves target users with strict boundary controls:
- **Authority Users**: Scoped to the incident's organization and region. Zero cross-organization leakage.
- **Responders**: Scoped strictly to the assigned responder or unit members.
- **Tourists**: Cleaned message payloads without internal notes, anomaly scores, or responder private data.
- **Emergency Contacts**: Filtered by tourist relationship and consent without duplicate spamming.
- **Preferences & Quiet Hours**: User quiet hours suppress non-mandatory notifications to silent in-app records, but **CANNOT** suppress mandatory emergency notifications (SOS, active incidents, responder assignments).

---

## 8. Template Engine & Security Sanitization

- Supports versioned templates with multi-locale rendering (`en`, `es`, `hi`, fallback `en`).
- **Security Sanitization**:
  - Medical diagnoses and allergies are stripped from notification bodies.
  - Internal AI anomaly scores and model weights are filtered out.
  - High-precision GPS coordinates are rounded to 4 decimals (~11m) or replaced with friendly zone labels.

---

## 9. Durable Queue, Retries & Dead-Letter Queue (DLQ)

- **Exponential Backoff with Jitter**:
  $$\text{Delay} = \min(\text{max\_delay}, \text{initial\_delay} \times \text{multiplier}^{\text{attempt}-1}) \pm \text{jitter}$$
- **Error Classification**:
  - `TRANSIENT` (500s, network timeout): Retried up to 3 times.
  - `PERMANENT`, `INVALID_RECIPIENT`, `AUTH_FAILURE`: Immediately failed without wasteful retries.
- **Dead-Letter Queue (DLQ)**:
  - Notifications exhausting retries are saved to `notification_dead_letters`.
  - Authority administrators can inspect failed notifications, trigger manual retries, or cancel with audit notes via `/api/v1/admin/notifications/*`.
- **Idempotency**: Composite SHA-256 key deduplicates redundant dispatches.

---

## 10. Webhooks & Delivery Receipts

Endpoint: `POST /api/v1/notifications/webhooks/{provider}`
- Verifies provider signatures and `provider_event_id` idempotency.
- Transitions notification status from `SENT` $\rightarrow$ `DELIVERED` or `FAILED`.

---

## 11. REST API Reference

| Endpoint | Method | Role | Description |
| :--- | :--- | :--- | :--- |
| `/api/v1/notifications` | `GET` | Authenticated | Paginated in-app notifications (filters: `unread_only`, `category`, `priority`) |
| `/api/v1/notifications/unread-count` | `GET` | Authenticated | Unread count for notification bell badge |
| `/api/v1/notifications/{id}/read` | `POST` | Authenticated | Mark notification as read |
| `/api/v1/notifications/read-all` | `POST` | Authenticated | Mark all notifications as read |
| `/api/v1/notifications/preferences` | `GET` / `PATCH` | Authenticated | Notification channel preferences & quiet hours |
| `/api/v1/devices/register` | `POST` | Authenticated | Register push device token |
| `/api/v1/devices/{device_id}` | `DELETE` | Authenticated | Deregister push device |
| `/api/v1/notifications/webhooks/{provider}` | `POST` | Public / Verified | Carrier delivery receipts |
| `/api/v1/notifications/metrics` | `GET` | Authority / Admin | Delivery observability metrics |
| `/api/v1/admin/notifications/providers` | `GET` | Authority / Admin | Inspect provider adapter health |
| `/api/v1/admin/notifications/failed` | `GET` | Authority / Admin | List Dead-Letter Queue (DLQ) items |
| `/api/v1/admin/notifications/{id}/retry` | `POST` | Authority / Admin | Manually retry failed DLQ item |
| `/api/v1/admin/notifications/{id}/cancel` | `POST` | Authority / Admin | Cancel failed DLQ item |

---

## 12. Frontend UI Integration

- **`NotificationCenterModal.tsx`**: High-performance dark-mode notification drawer with category tabs (`All`, `Unread`, `Critical`, `Safety`, `Incidents`), priority badges, deep-link navigation, and instant WebSocket updates.
- **`NotificationBellButton.tsx`**: Reusable notification bell with live unread badge.
- Embedded into **Authority Command Dashboard**, **Tactical Responder Dashboard**, and **Tourist App**.
