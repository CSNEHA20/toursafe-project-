# TourSafe Authority Command Center & Live Operations Platform

## 1. Executive Summary & Architecture Overview

The **TourSafe Authority Command Center & Live Operations Platform** is the primary mission-critical, government-grade operational client interface designed for public safety authorities, tourism police, and disaster response dispatchers. 

The command center integrates:
- **Live Multi-Layer Operational Geospatial Map** (Tourists with safety state & staleness degradation, Responders with operational status & units, Incidents with severity pins, GeoJSON hazard zones with live occupancy counts).
- **Live Operational Incident & SOS Queues** (Urgency-sorted incident queues with server-calculated age and dedicated SOS card banners).
- **Incident Command Panel & Authoritative Actions** (Acknowledge, Assign/Reassign eligible units, Escalate with justifications, Resolve with categorized debriefs, and Close).
- **High-Throughput Deduplicated Realtime Event Stream** (Category-filtered live event feed with deduplication and sequence/timestamp monotonicity).
- **Operational KPI & Subsystem Health Bars** (Live counts for active tourists, open incidents, active SOS, active responders, unassigned incidents, elevated safety states, stale tracking, and 6-subsystem diagnostic health indicators).

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ TOURSAFE AUTHORITY COMMAND CENTER & LIVE OPERATIONS                                     │
├────────────────────────────────┬──────────────────────────────┬────────────────────────┤
│ LEFT PANEL: QUEUES & LISTS     │ CENTER PANEL: LIVE MAP       │ RIGHT PANEL: COMMAND   │
│ - Live Incident Queue          │ - Tourists Layer             │ - Incident Command     │
│ - Dedicated SOS Queue          │ - Responders Layer           │ - Timeline Audit       │
│ - Active Responder Units       │ - Incidents Layer            │ - Dispatch / Actions   │
│ - GeoJSON Hazard Zones         │ - Zones Layer (Occupancy)    │ - Tourist Profile      │
├────────────────────────────────┴──────────────────────────────┴────────────────────────┤
│ BOTTOM PANEL: REALTIME EVENT STREAM (ALL • INCIDENTS • SOS • SAFETY • ZONES • RESPOND) │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Authoritative Backend Snapshot & Synchronization Model

The command center follows an **Authoritative Snapshot + Realtime Stream** synchronization model:
1. **Initial Snapshot Load**: On initialization or refresh, the frontend invokes `GET /api/v1/authority/command-center/snapshot`. This returns all active non-closed incidents, active tourists, registered responders, active hazard zones, live KPIs, authority scope, and the authoritative server timestamp.
2. **Realtime WebSocket Channel Routing**: The authenticated WebSocket stream (`ws://localhost:8000/ws?token=...`) broadcasts operational events (`incident.*`, `sos.*`, `safety.*`, `anomaly.*`, `zone.*`, `responder.*`, `tourist.*`, `notification.*`).
3. **Reconnection Reconciliation**: When connection drops, the frontend displays `RECONNECTING` and retains last-known coordinates with stale badges. Upon re-establishing the WebSocket connection, the frontend automatically invokes `reconcileSnapshot()` to replace stale entities without missing event replay gaps.

---

## 3. Location Staleness & Safety State Engine

Locations degrade gracefully to prevent false assumptions of safety during telemetry interruptions:

| Staleness State | Time Delta ($\Delta t$) | Map Pin Style | Operational Meaning |
| :--- | :--- | :--- | :--- |
| **LIVE** | $\Delta t < 30\text{s}$ | High-contrast Vibrant Color | Actively streaming real GPS coordinates |
| **RECENT** | $30\text{s} \le \Delta t < 2\text{m}$ | Standard Semantic Color | Normal tracking interval |
| **STALE** | $2\text{m} \le \Delta t < 10\text{m}$ | Dimmed / Amber Badge | Telemetry degraded, display last known position |
| **UNKNOWN** | $\Delta t \ge 10\text{m}$ | Neutral Gray / Untracked Badge | Device offline / lost tracking; not marked safe |

### Safety States
- **NORMAL**: Green pin / safe boundary.
- **WATCH**: Yellow alert, heightened anomaly probability.
- **ELEVATED**: Orange alert, multi-signal threshold breached.
- **INCIDENT_CANDIDATE / INCIDENT**: Red critical pin, prioritized in command queue.
- **RECOVERING**: Indigo cooldown, verified safe post-incident.
- **UNKNOWN**: Distinct neutral state (never masked as safe).

---

## 4. Role-Based Access Control (RBAC) & Authority Jurisdiction Scoping

Data access and mutation actions enforce strict backend role authorization:

| Capability | View-Only | Operator | Supervisor | Admin |
| :--- | :---: | :---: | :---: | :---: |
| View Live Map & Snapshot | ✅ | ✅ | ✅ | ✅ |
| View Realtime Event Stream | ✅ | ✅ | ✅ | ✅ |
| Search Entities | ✅ | ✅ | ✅ | ✅ |
| Acknowledge Incident | ❌ | ✅ | ✅ | ✅ |
| Assign / Reassign Responder | ❌ | ✅ | ✅ | ✅ |
| Send Dispatch Messages | ❌ | ✅ | ✅ | ✅ |
| Escalate Incident | ❌ | ❌ | ✅ | ✅ |
| Resolve / Close Incident | ❌ | ❌ | ✅ | ✅ |
| Manage Zones / System Diagnostics | ❌ | ❌ | ❌ | ✅ |

### Authority Isolation
All snapshot queries and searches are automatically scoped to the officer's `organization_name`, `authority_id`, or `jurisdiction_code` (e.g. `IN-GOA-NORTH`), ensuring Authority A cannot inspect or mutate records from Authority B.

---

## 5. Fault Tolerance & Subsystem Diagnostics

The command center monitors 6 core subsystems in real time:
1. **Realtime WebSocket Cluster**: Connection status and channel routing health.
2. **Sensor Telemetry Ingestion**: Quality of incoming GPS and synchronized IMU stream rates.
3. **ML Anomaly Engine**: LSTM inference latency and model artifact health.
4. **Notification & Dispatch Service**: Delivery SLAs and dead-letter queue metrics.
5. **Geospatial Map Tile Service**: OpenStreetMap / Leaflet tile server responsiveness.
6. **Core Backend API**: Database and Redis connection health.
