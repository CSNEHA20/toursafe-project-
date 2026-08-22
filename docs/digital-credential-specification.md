# TourSafe Digital Tourist Credential Specification

## 1. Credential Model & Attributes

The `DigitalTouristCredential` is a cryptographically signed, versioned pass issued exclusively to tourists with an active `VERIFIED` identity status.

| Field | Type | Description |
|---|---|---|
| `id` | UUID (string) | Unique primary key |
| `credential_reference` | String | Opaque human-readable reference e.g. `TS-CRED-8A2F9B10C34D` |
| `user_id` | String | References User account |
| `identity_profile_id` | String | References Tourist Identity Profile |
| `version` | Integer | Incremental version number (1, 2, 3...) |
| `status` | Enum | `ACTIVE`, `EXPIRED`, `REVOKED`, `SUSPENDED`, `REPLACED` |
| `issued_at` | DateTime (UTC) | Timestamp of issuance |
| `expires_at` | DateTime (UTC) | Explicit expiration timestamp |
| `signature` | String | Cryptographic HMAC-SHA256 signature |
| `token_nonce` | Hex String | 32-character random nonce for rotation & replay prevention |

---

## 2. Cryptographic QR Format (`TSQR`)

The QR code encodes a compact URL-safe Base64 JSON envelope:

```
TSQR:{base64url_encoded_payload}
```

### Decoded Payload Structure
```json
{
  "ref": "TS-CRED-8A2F9B10C34D",
  "uid": "usr_99812481",
  "ver": 1,
  "exp": 1787375662,
  "nnc": "a1f09c8e23b4456789abcdef12345678",
  "sig": "3a8f192b0c4d5e6f7a8b9c0d1e2f3a4b"
}
```

---

## 3. Public Verification Endpoint & Rate Limiting

### Endpoint
`POST /api/v1/credentials/verify`

### Request Payload
```json
{
  "qr_payload": "TSQR:...",
  "credential_reference": "TS-CRED-8A2F9B10C34D",
  "verification_context": "authority_checkpoint"
}
```

### Sanitized Response
```json
{
  "credential_reference": "TS-CRED-8A2F9B10C34D",
  "result_code": "VALID",
  "is_valid": true,
  "status": "ACTIVE",
  "verified_name": "Elena Rostova",
  "nationality": "FRA",
  "issued_at": "2026-08-22T04:30:00Z",
  "expires_at": "2026-11-20T04:30:00Z",
  "verification_timestamp": "2026-08-22T04:45:00Z",
  "issuer": "TourSafe Trust Authority",
  "provider_type": "DEV_KYC_PROVIDER"
}
```

### Rate Limiting & Abuse Prevention
Verification queries are constrained to **60 requests per minute per IP / verifier context** with real-time audit recording in `credential_verification_logs`.
