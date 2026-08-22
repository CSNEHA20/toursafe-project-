# TourSafe External Integrations & Interoperability Platform

## 1. Architectural Overview

TourSafe is built on a **strict provider-independent integration layer**. Core domain and business engines (Incident Command, Safety Risk Fusion, Responder Dispatch, Geofencing, Tourist Credentialing) never interact directly with third-party SDKs, vendor-specific endpoints, proprietary auth headers, or raw external JSON response formats.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TOURSAFE DOMAIN CORE                            │
│  (Incidents, Safety Fusion, Geofencing, Responders, Tourist Identity)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Normalized Domain Invocations
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│             INTEGRATION & INTEROPERABILITY FRAMEWORK                   │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    Integration Registry                          │  │
│  ├─────────────────────────────────┬────────────────────────────────┤  │
│  │ Circuit Breaker (CLOSED/OPEN)   │ Bounded Exponential Backoff    │  │
│  ├─────────────────────────────────┼────────────────────────────────┤  │
│  │ Anti-Replay & Idempotency Mgr   │ SSRF & Private Network Shield  │  │
│  ├─────────────────────────────────┼────────────────────────────────┤  │
│  │ Automatic Fallback Router       │ Dead-Letter Queue (DLQ)        │  │
│  ├─────────────────────────────────┼────────────────────────────────┤  │
│  │ Inbound Webhook Normalizer      │ Versioned Outbound Publisher   │  │
│  └─────────────────────────────────┴────────────────────────────────┘  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Normalized Adapter Interface
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                           PROVIDER ADAPTERS                            │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───┐ │
│ │  Maps &  │ │Comms SMS/│ │Identity/ │ │ Weather  │ │Emergency │ │Gov│ │
│ │ Routing  │ │Voice/Push│ │   KYC    │ │ Alerts   │ │CAD Agency│ │CAD│ │
│ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └─┬─┘ │
└──────┼────────────┼────────────┼────────────┼────────────┼───────────┼─┘
       │            │            │            │            │           │
       ▼            ▼            ▼            ▼            ▼           ▼
  Google/Mapbox  Twilio/AWS   Persona/Digi  OpenMeteo   112/CAD CAD  Gov APIs
```

---

## 2. Core Resilience & Failure Isolation Guarantees

1. **Failure Isolation**: An external provider outage (e.g. SMS carrier gateway down, Maps API 500) will **never** crash TourSafe or block core incident lifecycles.
2. **Circuit Breakers**: Automatically trip from `CLOSED` to `OPEN` on exceeding consecutive failure thresholds (default: 5), fast-failing subsequent requests without consuming thread pools or starving network connections. After cooldown (default: 30s), single trial probes transition to `HALF_OPEN` and auto-recover to `CLOSED` upon verified health.
3. **Bounded Retries with Jitter**: Exponential backoff prevents thundering herds while guaranteeing non-infinite attempts.
4. **Idempotency Deduplication**: Duplicate request keys and repeated webhook event IDs are cached and returned cleanly without duplicate operational side effects.
5. **Dead-Letter Queue (DLQ)**: Operations failing after maximum retry attempts are persisted in the DLQ with sanitized payload summaries, error classifications, and authorized manual retry triggers.

---

## 3. Supported Adapter Categories

| Category | Normalized Capabilities | Default Implementations |
|---|---|---|
| **MAPS** | `geocode`, `reverseGeocode`, `calculate_route`, `eta` | `DevMapsAdapter`, `OpenStreetMapAdapter`, `GoogleMapsAdapter`, `MapboxAdapter` |
| **SMS** | `send_sms`, `delivery_receipt`, `provider_message_id` | `SMSAdapter` (Dev / Twilio / AWS SNS) |
| **VOICE** | `initiate_call`, `text_to_speech`, `ivr_flow` | `VoiceAdapter` (Dev / Twilio Voice) |
| **EMAIL** | `send_email`, `templates`, `bounce_tracking` | `EmailAdapter` (Dev / SendGrid / SES) |
| **PUSH** | `send_push`, `topic_broadcast`, `data_payloads` | `PushAdapter` (Prompt 14 FCM / APNS) |
| **IDENTITY / KYC** | `submit_verification`, `check_status`, `verify_signature` | `IdentityProviderAdapter`, `DevKYCAdapter` |
| **WEATHER** | `get_current_weather`, `get_severe_alerts` | `WeatherAdapter`, `DevWeatherAdapter`, `OpenMeteoAdapter` |
| **TRANSLATION** | `translate`, `language_detection`, token masking | `TranslationAdapter` (Preserves coordinates, IDs, callsigns) |
| **EMERGENCY SERVICE** | `create_emergency_request`, `update_status`, conflict resolution | `EmergencyServiceAdapter` (Dev CAD / 112 API) |
| **GOVERNMENT** | `query_public_advisories`, `submit_incident_report` | `GovernmentAuthorityAdapter` |
| **TOURISM** | `query_attractions`, `safety_bulletins` | `TourismDataAdapter` |
| **DOCUMENT** | `upload_document`, `encryption_vault` | `DocumentAdapter` |
