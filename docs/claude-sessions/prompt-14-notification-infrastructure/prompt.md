# TOURSAFE — PROMPT 14
## PRODUCTION-GRADE NOTIFICATION & COMMUNICATION INFRASTRUCTURE

### SCOPE & REQUIREMENTS
- notification domain & communication domain
- provider abstraction (In-App, Realtime, Push, SMS, Email, Voice)
- in-app notifications & notification center
- realtime notifications via WebSocket event bus
- push notification abstraction & device registration
- SMS abstraction & E.164 validation
- email abstraction & RFC validation
- voice-call abstraction & safety gating
- notification templates & multi-locale support
- template security sanitization (strip medical/AI scores, round GPS)
- notification policies & policy versioning (`notification-policy-v1`)
- recipient resolution (scoped authority, assigned responder, tourist, emergency contacts)
- priority hierarchy (LOW, NORMAL, HIGH, CRITICAL)
- durable retries & exponential backoff with jitter
- idempotency key deduplication (SHA-256)
- delivery status tracking (SENT != DELIVERED)
- dead-letter queue (DLQ) & administrative resolution
- notification preferences & quiet hours with mandatory emergency overrides
- emergency communication policy with multi-stage escalation
- provider webhooks with signature verification & event idempotency
- communication audit trail
- authority, responder, and tourist notification center UI
