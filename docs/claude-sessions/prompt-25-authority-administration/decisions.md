# Architectural & Governance Decisions — Prompt 25: Authority Administration, Policy Configuration & System Governance

## 1. Multi-Tier RBAC & Separation of Duties
- **Decision**: Distinct roles (`system_admin`, `authority_admin`, `supervisor`, `authority_operator`, `responder`, `tourist`) enforced strictly server-side on every REST route.
- **Rationale**: Front-end assertions cannot be trusted. In particular, the critical rule of Separation of Duties dictates that for safety-critical configuration modifications (weights, thresholds, response policies, escalation matrices), the author (`created_by`) cannot approve their own change (`created_by != approved_by`). A distinct supervisor or authority administrator must review and sign off.

## 2. Immutable Historical Integrity
- **Decision**: Historical operational records (incidents, timeline events, risk episodes, responder dispatches) bind to the immutable configuration/policy version in effect when they were triggered.
- **Rationale**: When an authority admin updates a geofence polygon or changes an escalation timeout, historical incident data must never be retroactively or silently mutated.

## 3. Atomic Activation & Dynamic Hot-Reloading
- **Decision**: Configuration activation transitions the approved version to `ACTIVE` and atomically marks the superseded active version as `RETIRED`. This immediately invalidates Redis caches and triggers in-memory reloads in `SafetyRulesConfig` and orchestrator services.
- **Rationale**: Eliminates partial application states and race conditions during production deployments.

## 4. Secret Scrubbing on Export & Forced Draft on Import
- **Decision**: Configuration exports strip API keys, database credentials, and secrets with `[REDACTED_SECRET]`. Configuration imports are strictly forced to `DRAFT` status and must pass full validation and multi-user approval.
- **Rationale**: Prevents accidental data leaks and stops unauthorized or malicious configurations from immediately going live in production upon import.
