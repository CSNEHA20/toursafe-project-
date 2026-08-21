# TourSafe Location Architecture — Real GPS Location Tracking Subsystem

## Overview
TourSafe provides a high-reliability, physical GPS-based location tracking pipeline designed for tourist safety monitoring across designated geographical zones. The subsystem spans mobile device sensor acquisition (foreground and background), permission lifecycle management, coordinate normalization and validation, monotonic sequence tracking, quality/jitter telemetry calculation, Redis-backed live state cache with time-to-live (TTL) staleness detection, MongoDB historical persistence with GeoJSON `2dsphere` indexing, and authenticated real-time WebSocket event broadcasting.

> [!IMPORTANT]
> **Scope Notice**: Prompt 5 implements the real GPS location tracking foundation only. Future prompts will integrate IMU sensor telemetry (50 Hz accelerometer/gyroscope), AI anomaly detection (LSTM), geo-fence entry/exit triggers, and emergency dispatch routing.

---

## Architecture Diagram

```
+-------------------------------------------------------------------------+
|                         Mobile Client (Expo / React Native)             |
|                                                                         |
|  [ Physical GPS / Location Hardware (expo-location) ]                   |
|                          │                                              |
|                          ▼                                              |
|         [ LocationPermissionService ]                                   |
|         (unknown -> requesting -> granted / denied / blocked)           |
|                          │                                              |
|                          ▼                                              |
|         [ LocationTrackingService ]                                     |
|         - Subscribes via watchPositionAsync (~1 Hz)                     |
|         - Normalizes LocationSample                                     |
|         - Validates Bounds & Monotonic Sequence                         |
|         - QualityCalculator (Observed Hz, Accuracy, Jitter)             |
|                          │                                              |
|             ┌────────────┴────────────┐                                 |
|             ▼                         ▼                                 |
|     [ useLocationStore ]       [ HTTP POST /api/v1/location/update ]    |
|   (Zustand State & UI)                │                                 |
+───────────────────────────────────────┼─────────────────────────────────+
                                        │
                                        ▼
+-------------------------------------------------------------------------+
|                       FastAPI Backend & Data Tier                       |
|                                                                         |
|  1. JWT Authentication & Role Verification (tourist role required)      |
|  2. Strict Payload Validation (Lat [-90,90], Lon [-180,180], Seq >= 1)  |
|  3. Ingest Pipeline:                                                    |
|     ├─► Redis Live Cache: `live_location:tourist:{id}` (TTL: 120s)      |
|     ├─► MongoDB Persistence: `location_history` (GeoJSON 2dsphere)      |
|     ├─► Tracking Session Update: `tracking_sessions`                    |
|     └─► Realtime Bus: Broadcast `location.updated`                     |
|              │                                                          |
|              ├───────────────────────────────┐                          |
|              ▼                               ▼                          |
|   `tourist:{tourist_id}`           `authority:operations`               |
|   (Tourist Private Channel)        (Command Map Live Marker Stream)     |
+-------------------------------------------------------------------------+
```

---

## 1. Expo Location Integration & Hardware Sensors
- Real physical device GPS fixes are acquired via `expo-location` with `Accuracy.High`.
- Foreground tracking target: `timeInterval: 1000` (1000ms target, ~1 Hz), `distanceInterval: 1` (1 meter delta threshold).
- Background tracking: registered via `expo-task-manager` under `TOURSAFE_BACKGROUND_LOCATION_TRACKING` with foreground service notifications on Android and `NSLocationAlwaysAndWhenInUseUsageDescription` on iOS.
- No simulated, random, or mock coordinates are used in the tracking pipeline.

---

## 2. Location Permission Lifecycle
The `LocationPermissionService` manages fine-grained permission states:
- `unknown`: Permission has not yet been requested.
- `requesting`: System dialog is actively presented.
- `granted`: User granted location access.
- `denied`: User denied access (can ask again).
- `blocked`: User selected "Never ask again" or platform restricted.
- `unavailable`: Hardware or location services are disabled on device.

> [!NOTE]
> Foreground permission is verified before requesting background tracking permission. Requests are cached to prevent repetitive permission prompts on re-render.

---

## 3. Location Sample Data Model
```typescript
interface LocationSample {
  location_id?: string;
  tourist_id?: string;
  device_id?: string;
  session_id: string;
  timestamp: string;          // ISO 8601 UTC
  latitude: number;           // degrees [-90.0, 90.0]
  longitude: number;          // degrees [-180.0, 180.0]
  altitude?: number | null;   // meters above sea level
  accuracy?: number | null;   // horizontal accuracy in meters (>= 0)
  speed?: number | null;      // meters per second (>= 0)
  heading?: number | null;    // true heading in degrees [0.0, 360.0]
  provider?: string;          // "gps", "fused", "network"
  is_background: boolean;     // whether captured by background service
  network_status?: string;    // "online", "cellular", "wifi"
  sequence_number: number;    // monotonically increasing integer (>= 1)
}
```

---

## 4. Location Quality & Telemetry Metrics
Rather than assuming a theoretical 1 Hz rate, the `QualityCalculator` measures actual physical GPS performance over a rolling window (30 samples):
- **Sample Count**: Total validated GPS fixes received in current session.
- **Observed Frequency (Hz)**: Actual calculated update rate ($1000 / \text{avgIntervalMs}$).
- **Interval Metrics**: Minimum, maximum, and average interval between consecutive fixes in milliseconds.
- **Quality States**:
  - `excellent`: Horizontal accuracy $\le 10\text{m}$, interval $\le 3000\text{ms}$.
  - `good`: Horizontal accuracy $\le 25\text{m}$, interval $\le 8000\text{ms}$.
  - `degraded`: Horizontal accuracy $\le 50\text{m}$, interval $\le 15000\text{ms}$.
  - `poor`: Horizontal accuracy $> 50\text{m}$.
  - `stale`: Last sample $> 15\text{s}$ old.
  - `unavailable`: No active GPS fixes.

---

## 5. Redis Live Location Cache & Staleness Model
- **Key Schema**: `live_location:tourist:{tourist_id}`
- **TTL**: 120 seconds (2 minutes).
- **Backend Staleness Evaluation**:
  - `LIVE`: Sample timestamp is $\le 15\text{s}$ old.
  - `RECENT`: Sample timestamp is $\le 60\text{s}$ old.
  - `STALE`: Sample timestamp is $\le 300\text{s}$ old or Redis TTL has expired.
  - `UNKNOWN`: Sample timestamp is $> 300\text{s}$ old or no location fix exists.

---

## 6. MongoDB Historical Persistence & Geospatial Indexing
- **Collection**: `location_history`
- **GeoJSON Point**:
  ```json
  {
    "type": "Point",
    "coordinates": [77.4892, 10.2381]
  }
  ```
  *(Note: GeoJSON format requires `[longitude, latitude]` order).*
- **Indexes**:
  1. `[("location", "2dsphere")]`: Geospatial index for proximity queries.
  2. `[("tourist_id", 1), ("timestamp", -1)]`: Compound index for tourist historical breadcrumb trails.
  3. `[("session_id", 1), ("timestamp", -1)]`: Compound index for tracking session replay.
  4. `[("timestamp", -1)]`: Temporal index for system-wide range queries.

---

## 7. Realtime Event Architecture
When an authorized GPS fix arrives at `POST /api/v1/location/update`:
1. The payload is validated and persisted.
2. A canonical `RealtimeEventEnvelope` is formed:
   ```json
   {
     "event_id": "evt_abc123",
     "event_type": "location.updated",
     "timestamp": "2026-08-21T10:30:00.000Z",
     "source": "gps_tracking_pipeline",
     "version": 1,
     "payload": {
       "tourist_id": "tourist_123",
       "session_id": "sess_456",
       "location": {
         "latitude": 10.2381,
         "longitude": 77.4892,
         "altitude": 2133.0,
         "accuracy": 4.2,
         "speed": 1.2,
         "heading": 90.0,
         "is_background": false
       },
       "timestamp": "2026-08-21T10:30:00.000Z",
       "sequence_number": 42,
       "tracking_status": "active"
     }
   }
   ```
3. Event is dispatched to `tourist:{tourist_id}` and `authority:operations` channels.
4. Authority Command Map receives the update and moves the tourist marker in real time.

---

## 8. API Endpoint Matrix

| Method | Endpoint | Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/location/update` | Tourist | Ingest validated GPS fix; updates Redis, Mongo, and WebSocket stream. |
| `POST` | `/api/v1/location/session/start` | Tourist | Start / activate location tracking session. |
| `POST` | `/api/v1/location/session/stop` | Tourist | Stop active location tracking session. |
| `GET` | `/api/v1/tourists/me/location` | Tourist | Retrieve caller's latest live location and staleness status. |
| `GET` | `/api/v1/tourists/me/location-history` | Tourist | Retrieve caller's paginated historical location trail. |
| `GET` | `/api/v1/authority/tourists/{id}/location` | Authority | Inspect specific tourist's live location and staleness. |
| `GET` | `/api/v1/authority/tourists/{id}/location-history` | Authority | Inspect specific tourist's historical track. |
| `GET` | `/api/v1/authority/live-locations` | Authority | Retrieve all active live tourist locations for Command Map. |

---

## 9. Privacy & Security Protections
- **Zero-Trust Identity**: `tourist_id` is never accepted from the request body; it is always derived securely from the authenticated JWT session context.
- **Role-Based Access Control**: Authority endpoints strictly reject tourist tokens with HTTP 403 Forbidden.
- **Sanitized Logging**: Precise coordinates are excluded from raw operational logs and unhandled error responses.
