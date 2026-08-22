# Prompt 20 Architecture & UX Decisions

## 1. Safety Companion vs Surveillance Model
- **Decision**: Avoid all invasive terminology ("surveillance", "tracking subject", "AI anomaly threshold breach") in tourist-facing UI.
- **Rationale**: Building trust with tourists is paramount. Reassuring, actionable language ("We noticed unusual movement. Are you okay?") increases user engagement and consent retention while eliminating panic.

## 2. Strict Backend-Authoritative Safety State
- **Decision**: The mobile client never computes or overrides safety statuses (`SAFE`, `WATCH`, `ELEVATED`, `INCIDENT`, `UNKNOWN`).
- **Rationale**: The backend command center incorporates multi-source intelligence (geofences, regional weather alerts, police reports, crowd density). The client simply presents this authoritative state and facilitates tourist responses.

## 3. Deliberate 5-Second SOS Countdown
- **Decision**: Implement a 5-second countdown with haptic feedback and a prominent "Cancel Dispatch" button prior to transmitting emergency signals.
- **Rationale**: False alarms waste valuable emergency responder resources. The countdown allows tourists to abort accidental touches while ensuring instantaneous trigger if uncancelled.

## 4. Bounded Local Offline FIFO Buffer
- **Decision**: Limit the offline telemetry buffer to 5,000 packets with FIFO pruning and AsyncStorage durability.
- **Rationale**: Prevents mobile device memory leaks and out-of-storage crashes during prolonged network outages (e.g. multi-day trekking) while guaranteeing latest positions are retained.

## 5. Synchronous Trip and Tracking Session Binding
- **Decision**: Completing a trip in `itinerary.tsx` automatically executes graceful shutdown on active GPS and motion tracking sessions.
- **Rationale**: Preserves tourist battery life when vacations conclude and prevents accidental background monitoring after the trip is done.
