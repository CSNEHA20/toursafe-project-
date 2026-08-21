# TourSafe Real-Time Communication Architecture

## 1. Overview & Transport Strategy

TourSafe provides a high-reliability, low-latency real-time communication infrastructure designed for mission-critical tourist safety, emergency broadcast, and operational coordination across authorities and tourists.

```
                    TOURSAFE CLIENTS (Expo / React Native)
                                      │
                        authenticated WebSocket connection
                                      │
                                      ▼
                        FASTAPI REALTIME WEBSOCKET
                           (/ws & /api/v1/ws)
                                      │
                   ┌──────────────────┴──────────────────┐
                   │                                     │
           Client Channels                       Authority Channels
           user:{user_id}                        authority:operations
           tourist:{tourist_id}                  authority:{authority_id}
           zone:{zone_id}                        incident:{incident_id}
                   │                                     │
                   └──────────────────┬──────────────────┘
                                      │
                             Realtime Event Bus
                                      │
                  ┌───────────────────┼───────────────────┐
                  │                   │                   │
               MongoDB              Redis             Future AI /
             persistence      live caching / pub-sub  anomaly events
                  │                   │                   │
                  └───────────────────┼───────────────────┘
                                      │
                                      ▼
                             AUTHORITY OPERATORS
```

---

## 2. Native WebSocket vs Socket.IO Responsibilities

| Dimension | Native WebSocket (TourSafe Choice) | Socket.IO |
| :--- | :--- | :--- |
| **High-Frequency Telemetry (50 Hz)** | **Zero-overhead framing**, supports raw binary/JSON streaming directly into asyncio coroutines. | High frame wrapping overhead, polling fallbacks, and connection multiplexing overhead. |
| **Memory Footprint** | Extremely lightweight; low RAM per active socket. | Higher memory footprint due to session state, polling queues, and HTTP long-poll fallbacks. |
| **React Native / Expo Compatibility** | **Native runtime standard** across iOS, Android, and Web without third-party C++ bindings. | Requires polyfills or engine.io wrapper packages that complicate Hermes engine builds. |
| **Backpressure Control** | Native TCP flow control with asynchronous message handling. | Virtual buffers that can accumulate unconsumed messages during network jitter. |

### Architectural Separation
- **High-Frequency Telemetry Transport (Future Module)**: Operates over dedicated lightweight WebSocket streams designed for sensor timeseries processing without UI event queue contention.
- **Application Event Distribution**: Employs canonical JSON-enveloped event contracts broadcast across role-authorized logical channels.

---

## 3. Authentication & Connection Handshake

All real-time connections require cryptographic JWT authentication:

1. **Token Transport**: Client supplies JWT access token via query parameter `?token=<JWT>` or immediate initial authentication frame `{"action": "auth", "token": "<JWT>"}`.
2. **Token Verification**: Server decodes and verifies token signature using HS256 and validates expiration.
3. **Identity Resolution**: Resolves `user_id`, `role` (`tourist`, `authority`, `admin`), and profile status. Inactive users are rejected.
4. **Channel Assignment**: Initializes baseline authorized channels:
   - Tourist: `user:{user_id}`, `tourist:{tourist_id}`
   - Authority: `user:{user_id}`, `authority:{authority_id}`, `authority:operations`
   - Admin: All operational and diagnostic channels.
5. **Handshake Ack**: Server transmits `system.connected` event envelope containing `connection_id`, `user_id`, `role`, and assigned channels.

---

## 4. Connection Manager & Context Tracking

The backend `ConnectionManager` maintains four in-memory lookup indexes protected by asynchronous locking:

```python
class ConnectionManager:
    _active_connections: Dict[str, ConnectionContext]   # connection_id -> context
    _user_connections:   Dict[str, Set[str]]           # user_id -> set of connection_ids
    _role_connections:   Dict[str, Set[str]]           # role -> set of connection_ids
    _channel_subscribers: Dict[str, Set[str]]          # channel -> set of connection_ids
```

### Connection Lifecycle Management:
- **Multi-Device Support**: Users can connect concurrently from multiple devices; the manager routes to all active device sockets belonging to that user ID.
- **Graceful Disconnection**: On TCP close or timeout, the manager discards all references across user, role, and channel sets without memory leaks.
- **Fault-Tolerant Delivery**: If writing to a socket encounters a broken pipe or network drop, the manager automatically disconnects and cleans up the dead socket.

---

## 5. Logical Channels & Role-Based Authorization

TourSafe restricts channel subscriptions using deterministic role-based access control (RBAC):

| Channel Pattern | Intended Scope | Authorization Rule |
| :--- | :--- | :--- |
| `user:{user_id}` | Private user alerts | Only the matching `user_id` or `admin`. |
| `tourist:{tourist_id}` | Tourist state & telemetry | Matching tourist profile, or role in `['authority', 'admin']`. |
| `authority:{authority_id}` | Authority-specific dispatches | Matching authority profile or `admin`. |
| `authority:operations` | Live command center operational events | Strictly `authority` and `admin`. **Tourists rejected**. |
| `zone:{zone_id}` | Geospatial zone status updates | **All authenticated users** (tourists, authorities, admins). |
| `incident:{incident_id}` | Specific SOS / Emergency incident | Assigned authorities, admins, and the reporting tourist. |

---

## 6. Canonical Realtime Event Envelope (Version 1)

Every event delivered across TourSafe conforms to the canonical envelope contract:

```json
{
  "event_id": "evt_4a9b2c8f1e0d",
  "event_type": "zone.status_changed",
  "timestamp": "2026-08-21T10:15:30.123Z",
  "source": "backend",
  "version": 1,
  "payload": {
    "zone_id": "zone_kodaikanal_lake",
    "status": "warning",
    "reason": "Heavy fog and visibility drop"
  }
}
```

### Structural Rules:
- **No arbitrary top-level fields**: All event-specific metadata resides inside `payload`.
- **Versioning**: Explicit `version: 1` ensures backwards compatibility as schemas evolve.
- **Event IDs**: Generated uniquely with prefix `evt_` for end-to-end tracing and deduplication.

---

## 7. Centralized Event Registry

The event registry defines contracts across core TourSafe domains:

| Category | Event Types | Description |
| :--- | :--- | :--- |
| **SYSTEM** | `system.connected`<br>`system.disconnected`<br>`system.status`<br>`system.heartbeat`<br>`system.error` | Connection lifecycle, ping/pong keepalives, and operational notifications. |
| **TOURIST** | `tourist.profile.updated`<br>`tourist.status.updated` | Tourist safety status, profile changes, and check-in updates. |
| **LOCATION** | `location.updated`<br>`location.stale` | Device coordinate streaming and signal staleness detection. |
| **ZONE** | `zone.created`<br>`zone.updated`<br>`zone.status_changed` | Geospatial boundary modifications, risk level updates, and curfew changes. |
| **ALERT** | `alert.created`<br>`alert.updated`<br>`alert.resolved` | Broadcast safety warnings and severity updates. |
| **SOS** | `sos.created`<br>`sos.updated`<br>`sos.resolved` | Distress signal activation and emergency state progression. |
| **TELEMETRY** | `telemetry.started`<br>`telemetry.stopped`<br>`telemetry.status` | High-frequency sensor ingestion session lifecycle. |
| **AI** | `anomaly.detected`<br>`anomaly.confirmed`<br>`anomaly.cleared` | Machine learning anomaly triggers and safety verifications. |
| **EMERGENCY** | `emergency.created`<br>`emergency.updated`<br>`emergency.dispatched` | Responder dispatch and incident assignment. |
| **IDENTITY** | `identity.verified`<br>`identity.access_granted`<br>`identity.access_revoked` | KYC validation and digital identity lifecycle. |
| **E-FIR** | `efir.created`<br>`efir.updated`<br>`efir.dispatched` | Electronic police report filings and status updates. |

---

## 8. Frontend Realtime Client & Event Dispatcher

### Centralized Realtime Client (`frontend/lib/realtimeClient.ts`)
- **Singleton Lifecycle**: Exactly one managed WebSocket connection per application session.
- **Automatic Reconnection**: Reconnects with exponential backoff and randomized jitter (1s, 2s, 4s, 8s, up to 10s max delay).
- **Subscription Persistence**: Re-subscribes to all active channels automatically when network connection recovers.
- **Heartbeat Ping/Pong**: Dispatches periodic `{"action": "ping"}` keepalives every 25 seconds to prevent intermediate proxy timeout.

### Centralized Event Dispatcher (`frontend/lib/eventDispatcher.ts`)
Decouples React components from direct WebSocket dependencies by routing incoming events directly to Zustand state stores:
- `zone.*` → updates `useMapStore`
- `alert.*` → updates `useAlertStore`
- `sos.*` → updates `useSOSStore`

---

## 9. Redis Role & Graceful Degradation

Redis is prepared as an auxiliary caching and pub/sub layer:
- **Live GPS & Ephemeral State**: Stores high-frequency latest coordinates without overloading persistent MongoDB storage.
- **Health Check & Graceful Fallback**: If Redis is offline, TourSafe operates in standalone memory mode and reports `degraded` health status without service outage.
- **Authoritative Database**: MongoDB remains the persistent source of truth for zones, users, profiles, and audit records.

---

## 10. Security & Abuse Prevention

1. **Payload Size Limitation**: Enforces a 64 KB limit on application WebSocket frames (`WS_MAX_PAYLOAD_BYTES`), preventing memory exhaustion attacks.
2. **Channel Authorization Checks**: Every `subscribe` action is evaluated against `can_subscribe_to_channel` rules before registering the connection.
3. **Structured Sanitized Logging**: Real-time logs record event types, IDs, and connection channels while strictly redacting JWT tokens, passwords, medical data, and personal identifiable information (PII).
4. **Token Expiry Rejection**: Expired tokens immediately trigger WebSocket disconnection with code `1008` (Policy Violation).

---

## 11. Why High-Frequency Telemetry Must Not Mix with Normal UI Events

High-frequency sensor telemetry (such as future 50 Hz accelerometer, gyroscope, and raw GPS streams) generates ~50 packets/sec per active tourist.

### Architectural Risks of Merging Streams:
1. **Event Loop Starvation**: Saturating the UI event bus with 50 Hz messages causes React state re-render cascades, dropped UI frames, and sluggish user interactions.
2. **Queue Contention**: Critical low-frequency alerts (e.g. SOS dispatch, high-risk zone warnings) could be delayed behind high-volume sensor buffers during network congestion.
3. **Serialization Costs**: Serializing 50 Hz JSON envelopes produces significant garbage collection pressure on mobile Hermes/V8 runtimes.

### Solution:
TourSafe decouples the transport channels. Sensor telemetry will ingest through high-throughput streaming pipelines directly to ingestion workers, while user interface updates and operational alerts travel through the canonical `RealtimeEventEnvelope` bus.
