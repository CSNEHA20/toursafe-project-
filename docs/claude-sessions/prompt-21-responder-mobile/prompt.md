# Prompt 21: Responder Mobile Application & Field Operations

## User Prompt Summary
Build a dedicated, production-ready Responder-facing mobile application and field operations experience for TourSafe.
This is a FIELD OPERATIONS APPLICATION. Do not build a generic dashboard.

Key capabilities required:
1. Responder Availability & Shift Management (OFFLINE, AVAILABLE, UNAVAILABLE, ASSIGNED, RESPONDING, ON_SCENE).
2. Live Assignment Acceptance / Rejection with mandatory structured operational reasons.
3. Incident Command Dossier with privacy enforcement (minimal tourist PII, anomaly context, live location freshness).
4. Real-time GPS tracking & proximity-verified arrival with override fallback.
5. On-scene structured scene assessments (triage categorization, evidence/status, follow-up flags).
6. Tactical Field Notes with local queueing and idempotent batch synchronization in offline conditions.
7. Operational Handover workflow for fatigue, capability mismatch, or geographic barriers.
8. Incident resolution and mission closure returning responder to available pool.
9. Paginated mission history logs and telemetry diagnostics terminal.
10. Full backend validation test suite and TypeScript zero-error typing.
