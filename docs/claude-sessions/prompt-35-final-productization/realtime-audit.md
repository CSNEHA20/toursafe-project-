# Realtime Architecture & Event Bus Audit Report

## 1. Realtime Infrastructure Overview

TourSafe uses a resilient, dual-layered realtime architecture:
1. **Primary Protocol**: Persistent WebSocket channels managed by `frontend/lib/realtimeClient.ts`.
2. **Channel Bus**: Supabase Realtime Channels / FastAPI WebSocket ASGI endpoints.
3. **Event Dispatching**: Centralized single-source-of-truth dispatcher (`frontend/lib/eventDispatcher.ts`).

---

## 2. Event Envelope & Message Schema

Every realtime packet follows the standardized TourSafe event contract:

```typescript
interface RealtimeEnvelope<T = any> {
  event_type: string;        // e.g. "incident.created", "responder.location"
  event_id: string;          // UUID v4
  timestamp: string;         // ISO 8601 UTC
  source: string;            // e.g. "TourSafeInferenceEngine", "MobileGPS"
  jurisdiction_id?: string;  // Multi-tenant jurisdiction isolation
  payload: T;                // Typed event payload
}
```

---

## 3. Supported Realtime Event Types & Dispatch Handlers

| Event Type | Source Subsystem | Destination Store | Action Triggered |
| :--- | :--- | :--- | :--- |
| `incident.created` | SOS / Anomaly Engine | `commandCenterStore`, `sosStore` | Add incident to live triage queue, sound audible dispatch alert |
| `incident.updated` | Dispatcher / Responder | `commandCenterStore`, `sosStore` | Update status (`RESPONDER_ASSIGNED`, `RESOLVED`) |
| `responder.location` | Field GPS Telemetry | `commandCenterStore` | Update responder map marker coordinate, heading, and battery |
| `geofence.breached` | PostGIS Spatial Engine | `safetyStore`, `alertStore` | Trigger tourist geofence hazard alert modal |
| `telemetry.anomaly` | LSTM Inference Model | `safetyStore`, `commandCenterStore` | Update tourist safety risk score to ELEVATED |
| `notification.created` | Notification Engine | `NotificationCenterModal` | Increment unread badge count, render notification banner |

---

## 4. Reconnection & State Reconciliation

- **Heartbeat & Keepalive**: Client transmits ping every 30 seconds.
- **Backoff & Jitter**: Reconnection attempts use exponential backoff with random jitter (1s, 2s, 4s, 8s, max 30s).
- **Snapshot Reconciliation**: Upon reconnection, `commandCenterStore.fetchSnapshot()` automatically executes to fetch current state and resolve any dropped events during connection interruptions.
