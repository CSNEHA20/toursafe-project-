# Inbound Webhooks & Security Framework

## 1. Endpoint Structure

Inbound webhooks are received at:
`POST /api/v1/integrations/webhooks/{provider_type}/{provider_name}`

Example:
`POST /api/v1/integrations/webhooks/IDENTITY/DEV_KYC_PROVIDER`
`POST /api/v1/integrations/webhooks/EMERGENCY_SERVICE/DEV_EMERGENCY_CAD`

---

## 2. Security & Anti-Abuse Layers

```
Incoming Webhook Request
         │
         ▼
[1. Signature Verification] ──── Invalid ────► 401 Unauthorized
         │ Valid
         ▼
[2. Timestamp Window Check] ──── >300s old ──► 401 Stale Timestamp (Replay Rejected)
         │ Valid
         ▼
[3. Idempotency Nonce Check] ─── Duplicate ──► 200 OK (Cached Acknowledgment)
         │ New
         ▼
[4. Adapter Handler Execution] ─ Failed ─────► Dead-Letter Queue (DLQ)
         │ Success
         ▼
200 OK Normalized Event Processed
```

### A. Cryptographic HMAC Verification
- Webhooks verify HMAC-SHA256 signatures passed in `X-Signature-256` or `X-Hub-Signature-256` using timing-safe comparison (`hmac.compare_digest`).

### B. Anti-Replay Timestamp Windows
- Requests with timestamps deviating by more than 300 seconds (5 minutes) from current UTC time are rejected immediately to prevent network capture and replay attacks.

### C. Idempotency Deduplication
- Event IDs (e.g. `event_id`, `id`, `x-webhook-id`) are stored with payload SHA-256 digests in `IdempotencyManager`. Repeated webhooks receive an immediate `DUPLICATE_ACKNOWLEDGED` response without re-triggering business logic.
