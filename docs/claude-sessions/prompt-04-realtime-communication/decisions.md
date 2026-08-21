# Prompt 4 Architectural Decisions: Real-Time Communication Infrastructure

## Decision 1: Native WebSocket as Primary Real-Time Transport
- **Decision**: Use FastAPI native WebSockets (`/ws` and `/api/v1/ws`) and React Native standard `WebSocket` as the unified transport for both low-frequency application events and future high-frequency sensor telemetry.
- **Reason**: TourSafe requires future 50 Hz sensor telemetry (accelerometer, gyroscope) alongside UI alerts. Native WebSockets provide zero-overhead binary/text framing, lowest memory usage per socket, native ping/pong, and direct compatibility with Expo without requiring C++ engine.io bindings or polyfills.
- **Alternatives Considered**: Socket.IO, Server-Sent Events (SSE), Firebase Cloud Messaging (FCM).
- **Why Selected**: Socket.IO introduces significant frame wrapping overhead and polling fallback complexity that degrades high-frequency telemetry; SSE is unidirectional (cannot support client-to-server coordinate streaming); FCM is high-latency and unsuitable for live map tracking.

---

## Decision 2: Canonical Event Envelope (Version 1)
- **Decision**: Require all messages over the realtime event bus to strictly conform to `{ event_id, event_type, timestamp, source, version, payload }`.
- **Reason**: Standardizing on a single contract envelope guarantees that future components (AI anomalies, SOS orchestration, e-FIR dispatches) can publish and consume events without custom parsing logic or breaking version 1 consumers.
- **Alternatives Considered**: Direct arbitrary JSON dictionary emission or raw Socket.IO named events.
- **Why Selected**: Arbitrary structures cause brittle frontend dependencies; strict typed envelopes allow end-to-end tracing and clean schema evolution to `version: 2`.

---

## Decision 3: Deterministic Role-Based Channel Authorization
- **Decision**: Enforce server-side channel authorization rules inside `can_subscribe_to_channel` during the `subscribe` handshake rather than open broadcasting.
- **Reason**: TourSafe handles sensitive operational channels (`authority:operations`, `incident:{id}`) that must never be exposed to normal tourists, while public geospatial alerts (`zone:{id}`) must be freely receivable by all authenticated users.
- **Alternatives Considered**: Client-side filtering or single broadcast stream.
- **Why Selected**: Client-side filtering is a severe security vulnerability; server-enforced channel isolation ensures complete privacy and zero data leakage.

---

## Decision 4: Centralized Event Dispatcher in Frontend
- **Decision**: Decouple individual UI components from direct WebSocket connections by routing all incoming events through `initRealtimeEventDispatcher` directly into Zustand state stores (`useAlertStore`, `useMapStore`, `useSOSStore`).
- **Reason**: Avoids having individual screens create their own independent sockets or polling loops. Single socket instance connects once on app launch and updates global application state seamlessly.
- **Alternatives Considered**: Screen-level `useWebSocket` hook in each tab.
- **Why Selected**: Multiple WebSocket connections exhaust mobile battery and server connection limits. A singleton client with store dispatcher ensures instantaneous UI updates across all tabs simultaneously.

---

## Decision 5: Redis Graceful Degradation Strategy
- **Decision**: Prepare async Redis connection pooling and health checks, but allow TourSafe to operate gracefully in standalone in-memory mode if Redis is not configured or offline.
- **Reason**: In development or offline deployments, the entire TourSafe platform must remain operational with MongoDB and in-memory connection management without hard-failing due to missing Redis instances.
- **Alternatives Considered**: Making Redis a hard mandatory startup dependency.
- **Why Selected**: MongoDB remains the single authoritative persistent store; Redis is strictly an ephemeral caching optimization for live GPS state.
