# Prompt 14 Decisions

## 1. Complete Decoupling of Domain Events from Provider Delivery
- **Decision**: Domain models emit abstract domain events (`incident.created`, `sos.triggered`) rather than calling external communication providers directly.
- **Reason**: Tightly coupling incident workflows with third-party providers (Twilio, Firebase, SendGrid) creates brittle architectures, vendor lock-in, and unpredictable latency in critical emergency paths.
- **Alternatives Considered**: Direct helper calls in incident service.
- **Why Selected**: Decoupled architecture allows independent scaling, pluggable provider replacement, uniform retry policies, and centralized audit trails.

---

## 2. Strict Delivery Honesty (`NOT_CONFIGURED` & `SENT != DELIVERED`)
- **Decision**: External providers report `NOT_CONFIGURED` when API keys are absent, and mark notifications `SENT` (not `DELIVERED`) until confirmed by provider delivery receipts/webhooks.
- **Reason**: Safety-critical systems must never simulate false deliveries to users or authorities.
- **Alternatives Considered**: Mocking `DELIVERED` status automatically in development.
- **Why Selected**: Eliminates false confidence and strictly adheres to production safety guidelines.

---

## 3. Mandatory Emergency Quiet Hours Bypass
- **Decision**: User preferences and quiet hours apply only to optional categories (e.g. general updates, marketing). Mandatory emergency events (SOS, critical incident alerts, responder assignments) strictly bypass quiet hours and suppression filters.
- **Reason**: Safety and operational life-safety events cannot be muted by end-user settings.
- **Alternatives Considered**: Allowing users to mute all notifications.
- **Why Selected**: TourSafe is a safety orchestration system where critical responder and tourist alerts must be delivered unconditionally.

---

## 4. Voice Call Safety Gating
- **Decision**: Implemented `VoiceCallNotificationProvider` as an abstraction layer with `ENABLE_LIVE_VOICE_CALLS=false` default safety gating.
- **Reason**: Automated telephony systems risk unintended emergency calls, carrier spam flags, or compliance violations if invoked automatically without human dispatch confirmation.
- **Alternatives Considered**: Full auto-dial on every high incident.
- **Why Selected**: Safeguards against unintended 911/emergency dispatch while providing the complete infrastructural interface.
