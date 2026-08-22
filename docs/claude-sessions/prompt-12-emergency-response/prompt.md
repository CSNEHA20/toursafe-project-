# Prompt 12: Emergency Response Orchestration & Incident Command Center

## Prompt Specification Summary

The user requested implementation of the **Emergency Response Orchestration Layer** for TourSafe:
- **Core Mission**: Operationalize *"What happens operationally after an incident exists?"*
- **Operational Lifecycle**: `INCIDENT` $\to$ `AUTHORITY ALERT` $\to$ `ACKNOWLEDGEMENT` $\to$ `ASSESSMENT` $\to$ `ASSIGNMENT` $\to$ `RESPONSE` $\to$ `ESCALATION IF REQUIRED` $\to$ `RESOLUTION` $\to$ `CLOSURE`.
- **Key Modules**:
  1. Manual SOS Ingestion with client-request-id idempotency, active incident deduplication, and authoritative server GPS resolution with temporal staleness categorization.
  2. Incident Command Orchestration Service enforcing a strict state machine transition matrix, optimistic concurrency locking (`version`), immutable chronological timeline events (`TimelineEventRecord`), and operational notes threads (`IncidentNoteRecord`).
  3. Durable Escalation Engine driven by versioned YAML policies (`emergency_escalation_v1.yaml`), timeout evaluation sweeps, and stage-based idempotency keys (`{incident_id}:{stage}:{policy_version}`).
  4. Responder Management Service for registration, capability tagging, dispatch status tracking, and atomic release upon incident resolution.
  5. Notification System Abstraction supporting Push, SMS, Email, and Voice providers with honest status tracking (`NOT_CONFIGURED`, `DEVELOPMENT`, `SENT`, `FAILED`) without fabricating external carrier dispatches, plus automated emergency contact notification policies.
  6. Authenticated Realtime WebSocket Event Architecture publishing all incident lifecycle mutations to `authority:operations` and `tourist:{tourist_id}` channels.
  7. Frontend Admin Incident Command Center with operational metrics strip (MTTA, MTTR, false alarm rate), multi-filter searching, and an interactive Incident Command Modal.
  8. Frontend Tourist SOS UI with offline transmission queueing, active incident tracking, and tourist cancellation modal with mandatory explanation.
  9. Comprehensive backend automated test suite and architectural documentation.
