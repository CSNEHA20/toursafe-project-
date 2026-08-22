# Prompt 12: Architectural and Design Decisions

## Key Design Decisions

### 1. Separation of Safety Detection vs. Operational Incident Command
- **Context**: Prompt 11 determined *whether* a safety condition exists (`SafetySignal`, `rule_engine`, `SafetyStateMachine`). Prompt 12 determines *what operational workflow occurs* once an incident exists.
- **Decision**: Created a dedicated `IncidentCommandService` (`app.services.emergency.incident_service`) to govern operational state machine transitions (`OPEN`, `ACKNOWLEDGED`, `ASSESSING`, `ASSIGNED`, `RESPONDING`, `ESCALATED`, `RESOLVED`, `CANCELLED`, `CLOSED`), while Prompt 11's `SafetyOrchestrator` generates signals and initiates `IncidentRecord` entries.

### 2. Optimistic Concurrency Control
- **Context**: In multi-operator emergency response command rooms, two operators might simultaneously attempt to accept, assign, or resolve an incident.
- **Decision**: Added an integer `version` field to every `IncidentRecord`. State mutating endpoints take an optional `version` parameter and reject mutations where `expected_version != current_version` with `400 Bad Request`, preventing accidental overwrites.

### 3. Server-Authoritative GPS Resolution for Manual SOS
- **Context**: Mobile clients transmitting manual SOS may report inaccurate, stale, or spoofed GPS data.
- **Decision**: Manual SOS requests check `LocationService.get_live_location` for the latest server-validated GPS fix and calculate staleness (`CURRENT`, `STALE`, `NO_GPS`). Client-provided coordinates are stored strictly as secondary fallback hints with the `CLIENT_HINT` flag.

### 4. Honest Notification Provider Abstraction
- **Context**: The application must not simulate fake 911/police calls or pretend carrier SMS messages were sent when API credentials are absent.
- **Decision**: Built `NotificationProvider` abstractions where unconfigured providers explicitly set status to `NOT_CONFIGURED` (or `DEVELOPMENT` in test mode), persisting genuine delivery metadata in MongoDB.

### 5. Idempotent Multi-Stage Escalation
- **Context**: Periodic escalation sweeps across open incidents could repeatedly dispatch duplicate alerts.
- **Decision**: Implemented a composite idempotency key (`{incident_id}:{stage}:{policy_version}`) stored in `incident.escalation_history`. The escalation engine skips stages already marked as applied.

### 6. Atomic Responder Release on Resolution
- **Context**: When an incident is resolved or marked as a false alarm, the assigned responder must not remain locked in an assigned state.
- **Decision**: `incident_service.resolve_incident` and `cancel_incident` automatically call `responder_service.release_from_incident`, returning the responder's status to `AVAILABLE`.
