# TourSafe KYC Verification Workflow

## 1. KYC Lifecycle State Machine

```
NOT_STARTED
    │
    ▼ [POST /api/v1/kyc/start]
 PENDING
    │
    ▼ [POST /api/v1/kyc/documents] (Metadata + Masked ID)
UNDER_REVIEW ─────────┐
    │                 │ [POST /api/v1/authority/kyc/{id}/request-action]
    │                 ▼
    │           REQUIRES_ACTION
    │                 │
    │                 ▼ [POST /api/v1/kyc/documents] (Resubmission)
    │           UNDER_REVIEW
    │
    ├─── [POST /api/v1/authority/kyc/{id}/approve] ───► VERIFIED ──► [Credential Issued]
    │                                                     │
    │                                                     ▼ [Configured window elapses]
    │                                                   EXPIRED
    │
    └─── [POST /api/v1/authority/kyc/{id}/reject] ────► REJECTED
```

---

## 2. Structured Rejection Reasons

When an authority operator rejects a KYC submission, a structured reason is stored in the immutable verification history:

- `DOCUMENT_INVALID`: Document type or issuing country unsupported or recognized as invalid.
- `DOCUMENT_EXPIRED`: The submitted document has passed its legal expiry date.
- `DOCUMENT_UNREADABLE`: Low resolution, heavy glare, or cropped corners preventing review.
- `INFORMATION_MISMATCH`: The name or details on the document do not match the tourist profile.
- `VERIFICATION_FAILED`: Provider or authority automated checks failed.
- `OTHER`: Exceptional circumstances (accompanied by internal review notes).

---

## 3. Provider Abstraction & Status

The `IdentityVerificationProvider` base class allows pluggable integration with third-party verification providers (e.g., Stripe Identity, Persona, Veriff):

### Development Provider Disclaimer
The default provider is explicitly registered as:
```
DEV_KYC_PROVIDER
```
- **Real Provider Configured**: `False`
- **Purpose**: Provides automated state simulation for unit tests, end-to-end integration, and developer UI workflows.
- **Notice**: TourSafe UI and API responses explicitly distinguish between development simulations and legal government-backed verifications.

### Webhook Handling & Idempotency
Provider webhooks (`POST /api/v1/kyc/webhooks/{provider}`) require cryptographic HMAC-SHA256 signature verification (`X-Signature` header) and deduplicate events via in-memory/Redis idempotency caches to prevent double-approval or duplicate credential issuance.
