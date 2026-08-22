# TourSafe Queue & Dead-Letter Recovery Runbook

## 1. Queue Architecture & Resilience
Background jobs (notification delivery, telemetry aggregation, audit sync, external webhooks) run through async queues with bounded exponential backoff retries.

---

## 2. Dead-Letter Queue (DLQ) Management

### Inspection
Inspect dead-letter jobs:
```bash
curl -X GET "https://api.toursafe.io/api/v1/reliability/queues/dead-letter?limit=50" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

### Replay Execution
Replay a specific failed message idempotently:
```bash
curl -X POST https://api.toursafe.io/api/v1/reliability/queues/dead-letter/replay \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"job_id": "dlq-abc12345"}'
```

---

## 3. Stuck Job Remediation
- The `StuckJobWatchdog` scans for active async tasks running longer than 60 seconds.
- Hung tasks are cancelled with a timeout exception and moved to the DLQ to prevent thread starvation.
