# Prompt 17 - Mobile Edge & Sensor Intelligence - Key Decisions

## Decision: Battery-Aware Sampling Policies (Deterministic, Not ML-Driven)
- **Decision**: Implement configurable battery-aware sampling policies that are deterministic and bounded, rather than allowing an ML model to dynamically choose arbitrary sensor rates.
- **Reason**: Per prompt principle: "Policy must be deterministic and bounded. Do NOT allow an ML model to dynamically choose arbitrary sensor rates." Safety-critical tracking must have predictable behavior.
- **Alternatives Considered**:
  - ML-driven dynamic rates: Rejected - violates prompt principles, safety-critical unpredictability
  - Fixed rates only: Rejected - too rigid for real-world battery variations
  - Hybrid approach: Selected - deterministic policies with configurable thresholds
- **Why Selected**: Ensures predictable safety behavior, meets prompt requirements, no unexpected battery drain from erratic model behavior

## Decision: GPS Jump Filter (Mark, Don't Delete)
- **Decision**: Implement edge-side GPS jump detection that marks anomalies (GPS_ANOMALY/QUALITY_DEGRADED) rather than silently deleting GPS points.
- **Reason**: Per prompt principle: "Do not silently delete the point. Mark: GPS_ANOMALY or QUALITY_DEGRADED. Backend remains authoritative."
- **Alternatives Considered**:
  - Silent deletion: Rejected - loses data that could be valuable for backend analysis
  - Marking only: Selected - preserves data while flagging quality issues
  - Both marking and client-side correction: Rejected - oversteps mobile's role (backend authoritative)
- **Why Selected**: Maintains data integrity, provides quality metadata to backend, adheres to prompt principle

## Decision: at-Least-Once Delivery with Server-Side Idempotency
- **Decision**: Use at-least-once delivery with server-side idempotency, rather than assuming the mobile client can guarantee exactly-once delivery.
- **Reason**: Per prompt principle: "Do not assume the mobile client can guarantee exactly-once delivery. Use: at-least-once delivery with: server-side idempotency."
- **Alternatives Considered**:
  - Exactly-once client-side: Rejected - complex, error-prone, violates prompt principle
  - Best-effort without idempotency: Rejected - risk of duplicate processing
  - at-least-once with server idempotency: Selected - prompt-specified approach, robust
- **Why Selected**: Prompt-specified pattern, robust against network retries, simpler client implementation

## Decision: Privacy-Conscious Device ID (No Hardware Identifiers)
- **Decision**: Use a privacy-conscious application-scoped device identifier that does NOT collect IMEI, serial number, MAC address, or other unnecessary persistent hardware identifiers.
- **Reason**: Per prompt principle: "Do NOT collect unnecessary hardware identifiers. Do not expose: IMEI, serial number, MAC address or other unnecessary persistent hardware identifiers."
- **Alternatives Considered**:
  - IMEI/MAC-based ID: Rejected - violates privacy principles, prompt prohibits
  - Random UUID: Rejected - not tied to installation, loses consistency
  - Application-scoped deterministic ID: Selected - tied to app installation, no hardware identifiers
- **Why Selected**: Meets prompt privacy requirements, protects user privacy, still allows per-session tracking

## Decision: Exponential Backoff with Jitter (Max 5 Attempts)
- **Decision**: Implement exponential backoff with jitter for retry logic, with a maximum of 5 attempts. Permanent errors (403, 401, 400) are not retried.
- **Reason**: Per prompt principle: "Implement: exponential backoff, jitter, maximum attempts, retry classification. Do not retry permanent failures forever."
- **Alternatives Considered**:
  - Fixed retry delay: Rejected - doesn't adapt to network conditions
  - Infinite retry: Rejected - prompt principle: "Do not retry permanent failures forever"
  - Fixed number with linear backoff: Rejected - less efficient than exponential
  - Exponential with jitter, max 5: Selected - prompt-specified, robust
- **Why Selected**: Prompt-specified pattern, adapts to network conditions, prevents resource exhaustion

## Decision: GPS Accuracy Classification (Don't Discard Poor GPS)
- **Decision**: Record GPS accuracy and classify as GOOD/DEGRADED/POOR/UNKNOWN, but do not silently discard poor GPS data.
- **Reason**: Per prompt principle: "Do not treat every coordinate equally. Record: accuracy. Classify: GOOD/DEGRADED/POOR/UNKNOWN using configurable thresholds. Do not silently discard poor GPS. Mark quality."
- **Alternatives Considered**:
  - Discard poor accuracy: Rejected - loses data, violates prompt principle
  - Auto-correct GPS: Rejected - oversteps mobile role (backend authoritative)
  - Record and classify: Selected - prompt-specified approach
- **Why Selected**: Meets prompt requirements, provides quality metadata to backend, preserves data

## Decision: Tracking Session Explicit Lifecycle State Machine
- **Decision**: Implement tracking with an explicit lifecycle state machine (IDLE→STARTING→ACTIVE→PAUSED→OFFLINE→STOPPING→COMPLETED→ERROR) with validated transitions only.
- **Reason**: Per prompt principle: "Tracking must have an explicit lifecycle. Do not allow arbitrary state changes."
- **Alternatives Considered**:
  - No state machine: Rejected - arbitrary transitions, unpredictable behavior
  - Simple active/inactive: Rejected - too coarse, misses important states
  - Explicit state machine with validation: Selected - prompt-specified approach
- **Why Selected**: Predictable behavior, prevents invalid state transitions, meets prompt requirements

## Decision: Offline-First Telemetry Buffering
- **Decision**: Implement durable local buffering via AsyncStorage that survives component restart, app restart, and temporary network failure. Telemetry moves to LOCAL_BUFFER when network disappears.
- **Reason**: Per prompt principle: "The phone is a sensor and data collection edge node. The phone may perform: buffering. The system must continue functioning gracefully when: network disappears."
- **Alternatives Considered**:
  - No buffering: Rejected - data loss when network disappears
  - Memory-only buffering: Rejected - lost on component/app restart
  - AsyncStorage-backed FIFO: Selected - persistent, bounded, prompt-appropriate
- **Why Selected**: Persistent across restarts, bounded size (prevents memory exhaustion), prompt-specified approach

## Decision: Battery Critical Policy (Never Disable Safety-Critical Tracking)
- **Decision**: When battery is critical, reduce telemetry frequency but never completely disable safety-critical tracking.
- **Reason**: Per prompt principle: "Do NOT completely disable safety-critical tracking solely because battery is low."
- **Alternatives Considered**:
  - Disable tracking at low battery: Rejected - violates safety principle, prompt prohibition
  - Disable only GPS: Rejected - still consumes IMU, not comprehensive enough
  - Reduce frequency, preserve essential: Selected - prompt-specified approach
- **Why Selected**: Safety-critical per prompt requirements, protects user safety

## Decision: GPS/IMU Synchronization (Different Rates, No Forced Matching)
- **Decision**: GPS and IMU operate at different rates. Do NOT force every sensor to the same sampling frequency. Create synchronization metadata that preserves original sensor timestamps, canonical timestamps, sensor type, and sequence numbers.
- **Reason**: Per prompt principle: "GPS and IMU operate at different rates. Do NOT force every sensor to the same sampling frequency. Create synchronization metadata. The telemetry pipeline must preserve: original sensor timestamp, canonical timestamp, sensor type, sequence."
- **Alternatives Considered**:
  - Force to common frequency: Rejected - loses information, violates prompt principle
  - Different rates with interpolation: Rejected - introduces artifacts, overprocesses
  - Different rates with metadata: Selected - prompt-specified, minimal overhead
- **Why Selected**: Preserves data integrity, minimal client overhead, backend handles alignment (Prompt 16 dataset pipeline)

## Decision: SOS Resilience (Queued, Not Falsely Displayed)
- **Decision**: When SOS is triggered and network is unavailable, queue the SOS and retry. Do not falsely display "AUTHORITY NOTIFIED" until server acknowledgement exists.
- **Reason**: Per prompt principle: "SOS must remain the highest-priority mobile action. If network is unavailable: show: SOS QUEUED and retry. However: do not falsely display: AUTHORITY NOTIFIED until server acknowledgement exists."
- **Alternatives Considered**:
  - Immediately display authority notified: Rejected - false, violates trust, prompt prohibition
  - Don't SOS if no network: Rejected - defeats SOS purpose, violates prompt requirements
  - Queue and retry with delayed notification: Selected - prompt-specified approach
- **Why Selected**: User safety, honest UI, meets prompt requirements

## Decision: Contextual Permission Requesting
- **Decision**: Request permissions contextually (when needed for the task), rather than requesting all permissions at app launch.
- **Reason**: Per prompt principle: "Do not request all permissions at app launch. Request contextually."
- **Alternatives Considered**:
  - All permissions at launch: Rejected - overwhelming, privacy-averse, prompt prohibition
  - Request on first use: Selected - prompt-specified approach, better UX
- **Why Selected**: Better user experience, privacy-respecting, meets prompt requirements

## Decision: Background Execution Platform-Specific Implementation
- **Decision**: Implement background tracking using actual mobile platform capabilities. Android requires foreground service declaration; iOS has limited background capabilities. Do not claim continuous background sensor access if the OS does not guarantee it.
- **Reason**: Per prompt principle: "Implement using the actual mobile platform capabilities. Do not assume JavaScript timers continue reliably in the background. If React Native: inspect whether native background services/modules are required. Android and iOS have different restrictions."
- **Alternatives Considered**:
  - JavaScript timers in background: Rejected - not reliable, prompt prohibition
  - Same behavior on all platforms: Rejected - Android and iOS have different restrictions
  - Platform-specific implementation: Selected - prompt-specified, correct approach
- **Why Selected**: Honest about capabilities, meets prompt requirements, prevents false claims

## Decision: No Fake Production Data
- **Decision**: Production paths must use real device APIs. Synthetic data may exist only in tests, development, or explicit simulator/test mode. Mark synthetic data clearly as TEST DATA.
- **Reason**: Per prompt principle: "Production paths must use: real device APIs. Synthetic data may exist only in: tests, development, explicit simulator/test mode."
- **Alternatives Considered**:
  - Fake data in production: Rejected - violates prompt principle, undermines safety
  - No synthetic data anywhere: Rejected - useful for development/testing
  - Separate paths with clear marking: Selected - prompt-specified approach
- **Why Selected**: Meets prompt requirements, enables development/testing while protecting production

## Decision: Telemetry Schema Versioning (Separate from ML Feature Version)
- **Decision**: Mobile telemetry schema version is NOT the same as ML feature version. Keep separate: telemetry_schema_version, feature_version, model_version.
- **Reason**: Per prompt principle: "The mobile telemetry schema version is NOT the same as: ML feature version. Keep separate: telemetry_schema_version / feature_version / model_version."
- **Alternatives Considered**:
  - Single version field: Rejected - conflates different concerns, prompt prohibition
  - All versioning in one field: Rejected - loses separation of concerns
  - Separate fields for each: Selected - prompt-specified, clear separation
- **Why Selected**: Clear separation of concerns, meets prompt requirements, prevents schema mismatches

## Decision: Server Rate Limit Respect (429 Handling)
- **Decision**: If backend responds 429, respect Retry-After or equivalent, do not immediately retry repeatedly.
- **Reason**: Per prompt principle: "If backend responds: 429, respect: Retry-After or equivalent. Do not immediately retry repeatedly."
- **Alternatives Considered**:
  - Ignore 429: Rejected - will be rate-limited/banned
  - Immediate retry: Rejected - worsens rate limiting, could crash backend
  - Respect Retry-After: Selected - prompt-specified, courteous, effective
- **Why Selected**: Backend relationship, prevents being blocked, meets prompt requirements

## Decision: Dark Mode (Design Language)
- **Decision**: Follow the existing premium B2G/product design language: deep neutral, premium, readable, not pure black, not neon. Critical states should remain immediately distinguishable.
- **Reason**: Per prompt principle: "Follow the existing premium B2G/product design language."
- **Alternatives Considered**:
  - Pure black: Rejected - not readable, not premium, critical states lost
  - Neon colors: Rejected - not premium, accessibility issues
  - Design language match: Selected - consistent with existing product
- **Why Selected**: Visual consistency, readability, critical state visibility

## Decision: Accessibility (Color-Independent Status)
- **Decision**: Ensure GPS unavailable and other critical states are not communicated only through color. Provide large touch targets, screen-reader labels, clear status text, color-independent status, high contrast.
- **Reason**: Per prompt principle: "Do not communicate: GPS unavailable only through color."
- **Alternatives Considered**:
  - Color-only communication: Rejected - accessibility violation, prompt prohibition
  - Color + text labels: Selected - prompt-specified approach
  - Text-only: Rejected - less efficient for quick status scanning
- **Why Selected**: Accessibility compliance, prompt requirements, inclusive design

## Decision: Edge Preprocessing Limits
- **Decision**: Only implement lightweight preprocessing on-device. Examples: validation, normalization if required for transport, batching, compression if appropriate. Do NOT move the production LSTM to mobile in this prompt.
- **Reason**: Per prompt principle: "Only implement lightweight preprocessing on-device. Do NOT move the production LSTM to mobile in this prompt. Backend remains authoritative."
- **Alternatives Considered**:
  - Full LSTM on device: Rejected - violates prompt scope, overphones's role
  - No preprocessing: Rejected - transport quality could suffer
  - Lightweight only: Selected - prompt-specified balance
- **Why Selected**: Meets prompt requirements, protects backend authority, reasonable transport optimization

## Decision: No Mock Production Data
- **Decision**: Search for and eliminate mockGPS, fakeGPS, fakeAccelerometer, fakeGyroscope, randomTelemetry, demoTelemetry, fakeBattery, fakeSensor in production paths. Production paths must use real device APIs.
- **Reason**: Per prompt principle: "Production paths must use: real device APIs. Synthetic data may exist only in: tests, development, explicit simulator/test mode."
- **Alternatives Considered**:
  - Allow mock data in production: Rejected - violates prompt principle
  - Remove all synthetic data: Rejected - useful for development
  - Separate with clear marking: Selected - prompt-specified approach
- **Why Selected**: Meets prompt requirements, production integrity

## Summary of Decisions

| Decision | Key Principle |
|----------|--------------|
| Battery-aware sampling | Deterministic, not ML-driven |
| GPS jump filter | Mark, don't delete |
| Delivery | at-least-once + server idempotency |
| Device ID | Privacy-conscious, no hardware IDs |
| Retry | Exponential backoff, max 5, jitter |
| GPS accuracy | Classify, don't discard |
| Lifecycle | Explicit state machine |
| Offline buffering | AsyncStorage-backed FIFO |
| Battery critical | Reduce, never disable |
| GPS/IMU sync | Different rates, metadata |
| SOS resilience | Queue, don't falsely notify |
| Permissions | Contextual, not all at launch |
| Background | Platform-specific, honest |
| No mock production | Real device APIs only |
| Schema versioning | Separate: telemetry/feature/model |
| 429 handling | Respect Retry-After |
| Dark mode | Design language match |
| Accessibility | Color-independent + text |
| Edge preprocessing | Lightweight only |
| Mock data | Real APIs only, TEST DATA marked |

## Decision Log Summary

All decisions above follow prompt principles strictly. Each decision was made to comply with the strict scope defined in Prompt 17, ensuring:
- No client-side emergency dispatch
- No fake sensor data in production
- No autonomous safety decisions
- Backend remains authoritative
- Mobile is an edge node, not the decision engine
- Privacy-conscious design throughout
- Deterministic and bounded behavior where required
- Platform restrictions respected
- Privacy throughout