# TourSafe Tourist Mobile Architecture

## Overview & Principles
The TourSafe mobile application is designed as a **Tourist Safety Companion**, not a surveillance tracking system. The architecture guarantees:
1. **User Visibility & Agency**: The traveler always knows what data is collected, why, whether tracking is active, and whether telemetry is synced.
2. **Backend-Authoritative Safety State**: The client never independently classifies safety conditions or makes incident determinations. The frontend renders backend state and initiates deliberate user actions.
3. **Offline Resilience**: Bounded local FIFO queue (5000 records) with AsyncStorage persistence ensures complete continuity during network blackouts. Reconnection utilizes batching with idempotency keys (`client_request_id`).
4. **Adaptive Resource Management**: Dynamic frequency scaling and transmission tiering based on device battery level and connectivity quality.

---

## High-Level Architecture

```mermaid
graph TD
    subgraph "Mobile Device Client"
        Sensors[GPS & IMU Sensors] --> Pipeline[Telemetry & Jump Filter]
        Pipeline --> Buffer[Offline FIFO Buffer]
        Buffer --> ClientSync[Batch Dispatcher]
        
        UI[Tourist Mobile UI] --> Stores[Zustand State Stores]
        Stores --> TrackingSvc[Tracking Session Service]
        Stores --> EdgeSvc[Device Health & Battery Svc]
        
        WSClient[Realtime WS Client] --> EventDisp[Deduplicated Event Dispatcher]
        EventDisp --> Stores
    end

    subgraph "TourSafe Backend Services"
        ClientSync -->|HTTPS Batch API| Ingestion[/api/v1/telemetry/batch]
        TrackingSvc -->|Session APIs| LocationRouter[/api/v1/location]
        Stores -->|SOS / Incidents| EmergencyRouter[/api/v1/emergency]
        Stores -->|Trips / Itinerary| TouristRouter[/api/v1/tourists]
        Stores -->|KYC / Identity| IdentityRouter[/api/v1/identity]
        
        Redis[(Redis Pub/Sub)] --> WSGateway[FastAPI WebSocket Gateway]
        WSGateway --> WSClient
    end
```

---

## Core Subsystems

### 1. Tracking Session Lifecycle
State transitions are strictly validated through the `TrackingSessionService`:
```
IDLE ──► STARTING ──► ACTIVE ──► STOPPING ──► COMPLETED
                        │   ▲         │
                        ▼   │         ▼
                      PAUSED        ERROR
                        │   ▲
                        ▼   │
                     OFFLINE
```

- **Session Identification**: Every telemetry packet embeds `session_id`, originating from `/api/v1/location/session/start` or fallback local generation during disconnection.
- **Trip Association**: Completing a trip in `itinerary.tsx` automatically executes graceful shutdown on the tracking session.

### 2. Telemetry Pipeline & GPS Jump Filter
- **Haversine Speed Verification**: Inferred velocities $> 100\text{ m/s}$ are flagged as impossible jumps to eliminate GPS glitch false-positives.
- **Accuracy Classification**:
  - `GOOD`: $\le 10\text{m}$ horizontal accuracy.
  - `DEGRADED`: $\le 25\text{m}$ accuracy.
  - `POOR`: $> 25\text{m}$ accuracy.
  - `UNKNOWN` / `UNAVAILABLE`: No fix.
- **Battery-Aware Sampling**:
  - Normal ($> 20\%$): 50 Hz IMU, 1.0 Hz GPS.
  - Low ($6-20\%$): 10 Hz IMU, 0.2 Hz GPS, cellular uploads restricted.
  - Critical ($\le 5\%$): Sensor streaming paused, GPS minimal, emergency SOS prioritized.

### 3. Realtime Event Delivery & Deduplication
- Centralized WebSocket connection via `realtimeClient.ts`.
- `eventDispatcher.ts` enforces `event_id` deduplication via bounded memory cache.
- Dispatched domain events:
  - `SAFETY_STATUS_CHANGED`
  - `INCIDENT_UPDATE`
  - `SOS_ACKNOWLEDGED`
  - `ZONE_ENTRY` / `ZONE_EXIT`
  - `ANOMALY_FLAGGED`

---

## State Management Architecture (Zustand)

| Store | Primary Responsibilities |
|---|---|
| `useAuthStore` | Authentication tokens, user profile, role switching, identity cache |
| `useSafetyStore` | Backend authoritative safety status, safety check dialogs |
| `useTripStore` | Active trip, upcoming trips, completed trips, itinerary stops |
| `useLocationStore` | Live GPS fix, accuracy classification, tracking status |
| `useIMUStore` | Accelerometer & gyroscope telemetry stream, sampling rate |
| `useSOSStore` | SOS lifecycle states, active incident ID, assigned responder |
| `useGeofenceStore` | Monitored zones, active perimeter intersections, risk levels |
| `useBatteryStore` | Battery percentage, charging state, low power mode policy |
| `useConnectivityStore` | Network state (WiFi, Cellular, Offline), upload allowances |
| `useDeviceHealthStore`| Holistic health diagnostics, clock skew, sensor health |
| `useAlertStore` | Regional broadcasts, hazard warnings, system notices |
