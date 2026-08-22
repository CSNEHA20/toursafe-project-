# TourSafe Emergency Response Automation & Escalation Orchestration

## Overview

The **Emergency Response Automation & Escalation Orchestration Engine** converts operational safety events, geofence breaches, and manual SOS triggers into structured, policy-governed, auditable, and failure-tolerant incident response workflows.

It coordinates automatic capability-matched responder dispatches, strict multi-stage escalation chains with server-side acknowledgement timeouts, supervisor alerts, human-in-the-loop overrides, and full SLA lifecycle tracking.

```mermaid
flowchart TD
    A[Safety Anomaly / SOS Trigger] --> B[Incident Service]
    B --> C[Response Orchestrator]
    C --> D{Policy Resolver}
    D -->|Match Trigger & Zone| E[Response Plan & Action DAG]
    E --> F[Parallel Actions]
    F --> G[Notify Authorities]
    F --> H[Dispatch Responder]
    F --> I[Tourist Guidance]
    H --> J[Durable ACK Timer (Server-Side)]
    J -->|Accepted| K[Active Response & Arrival Tracking]
    J -->|Timeout / Declined| L[Escalation Stage 1: Secondary Redispatch]
    L -->|Timeout| M[Escalation Stage 2: Supervisor Escalation]
    M -->|Timeout| N[Escalation Stage 3: Emergency Broadcast]
    K --> O[Scene Assessment & Resolution]
    O --> P[Plan Completion & SLA Metrics]
```

---

## Key Architecture Components

### 1. Response Policy Service (`ResponsePolicyService`)
- **Configurable Policies**: Versioned response policies with trigger mapping (`SAFETY_STATE`, `MANUAL_SOS`, `GEOFENCE_HAZARD`, `OVERDUE_ITINERARY`, `ANOMALY_CLUSTER`).
- **Policy Lifecycle & States**: `DRAFT` $\rightarrow$ `TESTING` $\rightarrow$ `APPROVED` $\rightarrow$ `ACTIVE` $\rightarrow$ `RETIRED`.
- **Validation Engine**: Strictly enforces positive acknowledgement timeouts, valid action targets, and monotonic non-circular escalation stage graphs.
- **Simulation Sandbox**: Dry-run simulator for policies evaluating projected action execution graphs, stage progression, and SLA timelines without producing real incidents, dispatches, or notifications.
- **Rollback Engine**: Atomic rollbacks to older approved policy versions with mandatory rationale and audit logging.

### 2. Response Orchestrator (`ResponseOrchestrator`)
- **Dynamic Plan Creation**: Automatically initializes `ResponsePlanRecord` linked to incidents with unique action dependency graphs.
- **Action Dependency DAG Engine**: Independent actions (notifications, tourist guidance) run concurrently; dependent actions await prerequisite completion.
- **Durable Server-Side Timers**: Timer jobs persisted in MongoDB collection `response_timer_jobs` ensuring resilience across server restarts.
- **Distributed Concurrency Protection**: Atomic `find_one_and_update` status locking prevents double-escalations across clustered workers.
- **Automatic Multi-Stage Escalation**:
  - **Stage 0**: Capability-matched primary responder dispatch + initial notifications.
  - **Stage 1**: Secondary responder redispatch on acknowledgement timeout or decline.
  - **Stage 2**: Supervisor and authority command escalation.
  - **Stage 3**: Emergency broadcast and cross-jurisdictional notification.
- **Resilience & Fault Tolerance**:
  - Exponential backoff with bounded retries on transient action failures.
  - Automatic Dead-Letter Queue (DLQ) transitions for repeatedly failing actions.
  - No-eligible-responder fallback alerting command operators immediately.
- **Human-in-the-Loop Controls**:
  - Pause automation during operator investigations.
  - Resume automation with active state reconciliation.
  - Operator manual overrides (forced escalation, responder reassignment, status overrides).
  - Clean incident cancellation and resolution cancelling all active timers.

### 3. REST API Surface (`/api/v1/orchestration`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/policies` | List response policies (filterable by trigger & status) |
| `POST` | `/policies` | Create draft policy with schema validation |
| `GET` | `/policies/{id}` | Get policy detail |
| `PUT` | `/policies/{id}` | Update draft/testing policy |
| `POST` | `/policies/{id}/approve` | Approve policy for production deployment |
| `POST` | `/policies/{id}/activate` | Activate approved policy (retires previous active) |
| `POST` | `/policies/rollback` | Roll back active policy to previous version |
| `POST` | `/policies/simulate` | Pure dry-run simulation sandbox |
| `GET` | `/plans/{incident_id}` | Retrieve incident response plan, actions, active timers |
| `POST` | `/plans/{id}/pause` | Pause automated execution and timers |
| `POST` | `/plans/{id}/resume` | Resume automated execution |
| `POST` | `/plans/{id}/override` | Authorized manual operator override |
| `POST` | `/plans/{id}/actions/{action_id}/retry` | Retry failed action |
| `GET` | `/health` | Orchestrator health & external adapter status |
| `GET` | `/kpis` | Real calculated response performance KPIs |
| `POST` | `/sweep` | Trigger immediate durable scheduler sweep |

---

## State Transition Matrix

### Response Plan States
```
PENDING ──> ACTIVE ──> WAITING_ACK ──> RESPONDING ──> RESOLVING ──> COMPLETED
   │          │             │              │             │
   │          v             v              v             │
   └────> ESCALATING ───────┴──────────────┴─────────────┘
              │
              v (Cancelled / Resolved)
          CANCELLED / COMPLETED
```

---

## External Emergency Services Adapter Status

As required, adapters for national external emergency services (e.g. 112 / 911 / EMS CAD systems) are configured as unconnected stubs:
- **Status**: `NOT_CONNECTED`
- **Protocol**: Simulated webhook / dispatch stub with strict retry bounding and offline queueing.
