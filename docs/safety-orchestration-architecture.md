# TourSafe Safety Orchestration & Multi-Signal Risk Fusion Engine

## 1. Engine Philosophy & Architectural Foundation
The TourSafe Safety Orchestration Engine is the core intelligence and risk synthesis layer of the TourSafe platform. Its primary mission is to evaluate heterogeneous sensor streams, geospatial geofence containment states, LSTM Autoencoder kinematic motion anomaly scores, and sensor quality telemetry to compute an auditable, context-aware **Safety State** for each active tourist.

### Non-Negotiable Axioms:
1. **Multi-Signal Synthesis Over Single-Signal Reaction**: A single anomaly is *not* an emergency. A restricted zone entry is *not* an emergency. High acceleration is *not* an emergency. Poor GPS is *not* an emergency. Safety state is computed only through deterministic corroboration across independent domains.
2. **Safety State $\neq$ Emergency Dispatch**: The engine emits a structured, auditable `SafetyState` and lifecycle-managed `IncidentRecord`. It does *not* trigger automatic external emergency services, police dispatch, or SMS/phone alerts.
3. **No Risk $\neq$ No Data**: When GPS or IMU telemetry is disconnected, degraded, or stale, the tourist state is evaluated as `UNKNOWN` or degraded, never falsely assumed to be `NORMAL`.
4. **Deterministic Rule Evaluation**: All risk escalations are governed by `safety-rules-v1`. Given identical inputs, timestamps, and configurations, the engine deterministically yields identical decisions without stochastic drift or unvetted LLM interference.

---

## 2. Supported Safety States
The engine models tourist safety as an explicit finite state machine with strict transition gating:

| State | Semantic Description | Trigger Condition |
| :--- | :--- | :--- |
| `NORMAL` | Baseline nominal operations | All fresh signals within normal parameters. High quality GPS & telemetry. |
| `WATCH` | Initial transient divergence | Transient anomaly, approaching warning zone boundary, or minor sensor degradation. |
| `ELEVATED` | Corroborated elevated risk | Persistent anomaly $\ge 2$ windows OR active presence in a `restricted` zone. |
| `INCIDENT_CANDIDATE` | High-confidence danger precondition | Persistent anomaly ($\ge 4$ win) OR anomaly corroborated by `danger`/`restricted` zone. Requires 1 confirmation cycle. |
| `INCIDENT` | Active corroborated safety incident | Candidate state confirmed on consecutive evaluation cycle. Emits lifecycle incident record. |
| `RECOVERING` | Nominal stabilization period | All sensor streams return to normal after an incident. Enforces 20s cooldown before returning to `NORMAL`. |
| `UNKNOWN` | Degraded/Missing telemetry | GPS accuracy $> 50\text{m}$, telemetry sampling rate $< 35\text{Hz}$, or no heartbeat for $> 30\text{s}$. |
| `ERROR` | Engine execution exception | Internal parsing failure or invalid sensor packet format. |

---

## 3. Signal Ingestion & Multi-Signal Contract
Every sensor reading is normalized into a standard canonical `SafetySignal` envelope before entering the rule evaluation pipeline:
- **`GPS`**: Latitude, longitude, altitude, speed, bearing, horizontal accuracy (m), and freshness timestamp.
- **`ANOMALY`**: Reconstruction error score ($E_{\text{window}}$), threshold ($\tau_{\text{user}}$), consecutive anomaly window count, and model version (`lstm_autoencoder_v1`).
- **`GEOFENCE`**: Zone ID, zone type (`safe`, `warning`, `restricted`, `danger`), risk level (`low`, `medium`, `high`, `critical`), membership state (`inside`, `approaching`, `outside`), and geodesic boundary distance.
- **`TELEMETRY`**: Sample frequency (Hz), packet drop percentage, IMU jitter, battery level, and charging state.
- **`TRACKING`**: Session state (`active`, `paused`, `stale`, `completed`), duration, and heartbeat status.
- **`CONTEXT`**: Time of day, itinerary schedule alignment, remote trail difficulty rating, and group proximity.

---

## 4. Signal Freshness & Quality Thresholds
Safety signals automatically decay and expire based on domain-specific time-to-live (TTL) thresholds:
- **GPS Signal Freshness**: $30\text{ seconds}$ (Marked `STALE` if older).
- **Anomaly Signal Freshness**: $20\text{ seconds}$ (Marked `STALE` if older).
- **Telemetry Packet Freshness**: $15\text{ seconds}$ (Marked `STALE` if older).
- **Geofence Signal Freshness**: $60\text{ seconds}$ (Marked `STALE` if older).
- **Poor GPS Horizontal Accuracy Gating**: Accuracy $> 50\text{m}$ forces signal quality to `POOR` and caps safety state at `ELEVATED` (preventing spurious jumps to `INCIDENT`).
- **Telemetry Frequency Degradation**: Frequency $< 35\text{Hz}$ forces quality to `DEGRADED` and confidence class to `LOW`.

---

## 5. Deterministic Rule Engine (`safety-rules-v1`)
The rule engine evaluates 7 rule categories in strict hierarchical order:

### Category A: Anomaly Evaluation
- `RULE_A1_TRANSIENT_ANOMALY` (Weight 20): Transient anomalous motion window $\to$ `WATCH`.
- `RULE_A2_PERSISTENT_ANOMALY` (Weight 50): Anomaly lasting $\ge 2$ consecutive windows $\to$ `ELEVATED`.
- `RULE_A3_HIGH_SEVERITY_ANOMALY` (Weight 80): Anomaly lasting $\ge 4$ windows with score $> 1.5\times$ threshold $\to$ `INCIDENT_CANDIDATE`.

### Category B: Geofence Containment
- `RULE_B1_APPROACHING_RESTRICTED` (Weight 15): Distance to restricted zone $< 50\text{m}$ $\to$ `WATCH`.
- `RULE_B2_INSIDE_RESTRICTED_ZONE` (Weight 60): Inside restricted boundary $\to$ `ELEVATED`.
- `RULE_B3_INSIDE_DANGER_ZONE` (Weight 85): Inside designated danger zone $\to$ `INCIDENT_CANDIDATE`.

### Category C: Corroboration & Multi-Signal Fusion
- `RULE_C1_ANOMALY_AND_RESTRICTED_ZONE` (Weight 90): Active anomaly + restricted zone $\to$ `INCIDENT_CANDIDATE`.
- `RULE_C2_PERSISTENT_ANOMALY_AND_DANGER_ZONE` (Weight 100): Persistent anomaly + danger zone $\to$ `INCIDENT`.

### Category D: Signal Quality & Gating
- `RULE_D1_POOR_GPS_ACCURACY` (Weight 10): Accuracy $> 50\text{m}$ $\to$ Downgrades state cap to `ELEVATED`.
- `RULE_D2_DEGRADED_TELEMETRY` (Weight 10): Packet loss $> 20\%$ or freq $< 35\text{Hz}$ $\to$ Caps confidence at `LOW`.
- `RULE_D3_MISSING_DATA_UNKNOWN` (Weight 0): No fresh GPS or Telemetry $\to$ `UNKNOWN`.

### Category E: Recovery Cooldown
- `RULE_E1_RECOVERY_COOLDOWN_ACTIVE` (Weight 0): Stable nominal signals during recovery cooldown ($< 20\text{s}$) $\to$ Holds `RECOVERING`.
- `RULE_E2_RECOVERY_COOLDOWN_EXPIRED` (Weight 0): Stable nominal signals exceeding $20\text{s}$ cooldown $\to$ Transitions to `NORMAL`.

---

## 6. Incident Lifecycle State Machine
Safety incidents are auditable, deduplicated domain records managed through a five-stage lifecycle:
```
           +-----------------------------+
           |                             |
           v                             |
       [ OPEN ] ----------------> [ ACKNOWLEDGED ]
          |                              |
          |                              |
          v                              v
    [ MONITORING ]                [ MONITORING ]
          |                              |
          +--------------+---------------+
                         |
                         v
            [ RESOLVED ] / [ CANCELLED ]
```
- **`OPEN`**: Automatically created when `INCIDENT` state is reached. Deduplicated if an active incident already exists for the tourist.
- **`ACKNOWLEDGED`**: Claimed by an Authority operator with active timestamp and operator ID.
- **`MONITORING`**: Placed under continuous active observation while field verification occurs.
- **`RESOLVED`**: Closed with required resolution notes and justification.
- **`CANCELLED`**: Marked as a false alarm or test event.

---

## 7. Recovery & Cooldown Dynamics
When an incident or elevated risk condition abates (all sensors report nominal metrics), the engine enforces a strict **20-second Recovery Cooldown Period**:
1. State transitions from `INCIDENT` $\to$ `RECOVERING`.
2. A timer `recovery_started_at` is set in Redis ephemeral state and MongoDB active document.
3. Every evaluation cycle validates that all incoming signals remain nominal.
4. If an anomaly reoccurs within the 20 seconds, the recovery aborts and immediately reverts to `INCIDENT`.
5. If the 20 seconds elapse with zero anomaly signals, the state transitions cleanly back to `NORMAL`.

---

## 8. Ephemeral State & Redis Caching
High-frequency evaluations read from and write to Redis with zero disk I/O bottlenecks:
- **`toursafe:safety:state:{tourist_id}`**: JSON hash containing `current_state`, `previous_state`, `last_evaluated_at`, `active_incident_id`, `rule_version`, `quality`, and `recovery_started_at` (TTL 3600s).
- **`toursafe:safety:signals:{tourist_id}`**: Hash of the latest canonical signals for each signal type.
- **In-Memory Fallback**: When Redis is temporarily unavailable or in local test runners, the engine seamlessly utilizes thread-safe in-memory dictionary stores.
- **Cold-Start Reconstruction**: If the server restarts with empty cache, the engine queries the latest `safety_decisions` from MongoDB and rebuilds active state.

---

## 9. MongoDB Auditing & Immutability
All safety decisions and incident state changes are recorded permanently for audit and post-incident investigation:
- **Collection `safety_decisions`**: Immutable stream of every evaluated decision including `decision_id`, `tourist_id`, `state`, `confidence`, `quality`, `reasons`, `signals`, and `triggered_rules`. Indexed on `(tourist_id, timestamp DESC)`.
- **Collection `safety_incidents`**: Auditable incidents with tracking of `started_at`, `updated_at`, `status`, `severity`, `acknowledged_at`, `acknowledged_by`, `resolved_at`, and chronological operator notes. Indexed on `(tourist_id, status)` and `(status, created_at DESC)`.

---

## 10. Realtime Event Architecture & Channel Privacy
Safety state changes and incidents broadcast strongly-typed event envelopes via Redis PubSub and WebSockets:
- **Authority Channel (`authority:operations`)**: Receives full raw diagnostic envelopes containing detailed sensor scores, triggered rule weights, and internal decision IDs (`safety.state_changed`, `incident.created`, `incident.updated`, `incident.resolved`).
- **Tourist Channel (`tourist:{tourist_id}`)**: Receives sanitized, user-appropriate guidance messages to avoid inducing panic (e.g. *"Safety status: Normal - Enjoy your tour"* or *"Please slow down and remain on designated trails"*).

---

## 11. REST API Contracts

### Authority Endpoints:
- `GET /api/v1/authority/tourists/{tourist_id}/safety`: Retrieve active safety state, current signals, quality, and active incident ID.
- `GET /api/v1/authority/tourists/{tourist_id}/safety/history`: Paginated audit log of historical safety decisions.
- `GET /api/v1/authority/tourists/{tourist_id}/incidents`: Query active or historical incidents for a tourist.
- `GET /api/v1/authority/incidents`: Query all system-wide safety incidents with status and severity filters.
- `POST /api/v1/authority/incidents/{incident_id}/acknowledge`: Acknowledge an open incident.
- `POST /api/v1/authority/incidents/{incident_id}/resolve`: Resolve an active incident with required audit explanation.

### Tourist Endpoints:
- `GET /api/v1/tourists/me/safety`: Retrieve sanitized, user-friendly safety status and safety guidance.

---

## 12. Verification & Test Suite Summary
- **Total Unit & Integration Tests**: 20 comprehensive automated test scenarios in `test_safety_engine.py` and `test_safety_e2e.py`.
- **Full Backend Regression Suite**: 164 passed, 0 failed across all modules (Auth, KYC, Zones, Location, Telemetry, IMU, ML Inference, Realtime, Geofencing, Safety Orchestration).
- **Frontend Type Safety**: 0 TypeScript compilation errors (`npx tsc --noEmit`).
