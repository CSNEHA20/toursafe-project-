# TourSafe Identity & Verification Architecture

## 1. Overview & Core Principles

The TourSafe Identity, KYC, and Digital Tourist Credential platform provides a high-security, privacy-preserving verification layer connecting tourist identities with authority checkpoints, emergency operations, and verified access control.

```
USER ACCOUNT (Authentication & Credentials)
      ↓
TOURIST IDENTITY PROFILE (Privacy-Preserving Identity Domain)
      ↓
KYC VERIFICATION WORKFLOW (Pluggable Provider Abstraction + Review Queue)
      ↓
VERIFIED TOURIST STATUS (Strict Verification Gate)
      ↓
DIGITAL TOURIST CREDENTIAL (Cryptographically Signed Token + Nonce)
      ↓
OPAQUE QR PAYLOAD (TSQR Format)
      ↓
AUTHORITY CHECKPOINT VERIFICATION (Rate-Limited, Zero-Trust Sanitized DTO)
```

### Critical Zero-Trust Principle
Identity verification in TourSafe strictly answers:
> *"Has this identity/profile been verified according to the configured verification process?"*

It **NEVER** answers or implies:
- "Is this tourist safe?"
- "Is this tourist trustworthy?"
- "Is this tourist incident-free?"

TourSafe strictly prohibits the creation or inference of:
- Tourist trust scores
- Behavioral risk scores
- Demographic risk scores
- Social scores

---

## 2. Domain Separation

To protect sensitive user data and avoid tight coupling, the architecture enforces strict separation across 6 distinct domains:

1. **User Account**: Authoritative for credentials, JWT authentication, and RBAC roles (`tourist`, `authority`, `admin`, `responder`).
2. **Tourist Identity Profile**: Dedicated identity metadata domain (`full_name`, `date_of_birth`, `nationality`, `contact_info`, `identity_status`, `verified_fields`).
3. **KYC Document & Verification History**: Metadata-only records (`masked_identifier`, `storage_key`, `verification_status`, `rejection_reason`, reviewer audit log).
4. **Digital Tourist Credential**: Versioned issuance entity with cryptographic HMAC-SHA256 signature and rotating token nonces.
5. **Trip & Itinerary Operations**: Separate tracking and geospatial context; identity verification status is linked for operational awareness without exposing KYC files.
6. **Safety & Emergency Response**: Responders receive minimal operational views (name, emergency contacts, verified badge) during active incidents, never raw KYC docs.

---

## 3. Data Minimization & Role-Based DTOs

Database identity models are never returned directly over the wire. Instead, tailored DTOs enforce data minimization:

| View DTO | Recipient | Exposed Fields | Protected / Suppressed Fields |
|---|---|---|---|
| `TouristSelfIdentityView` | Authenticated Tourist | Full profile, document count, consent count, active credential reference | Internal reviewer notes, unmasked storage paths |
| `AuthorityTouristIdentityView` | Authorized Operator | Full name, DOB, nationality, masked documents, verification history count | Raw passwords, unmasked government ID numbers |
| `ResponderTouristIdentityView` | Emergency Responder | Full name, nationality, phone, verified badge, credential ref | KYC documents, historical rejections, internal review notes |
| `PublicVerificationResult` | Public / Checkpoint | Result code (`VALID`, `EXPIRED`, `REVOKED`, `SUSPENDED`, `INVALID`), verified name, validity dates | User ID, home address, emergency contacts, trip history |

---

## 4. Cryptographic Digital Credential & QR Token

Digital credentials feature cryptographic authenticity and replay resistance:

- **Algorithm**: HMAC-SHA256 over canonical string:
  `{credential_reference}:{user_id}:{version}:{expires_ts}:{token_nonce}`
- **QR Payload Format**:
  `TSQR:{base64url_encoded_json}`
  Containing `{ref, uid, ver, exp, nnc, sig}`.
- **Rotation**: Nonces can be rotated on-demand (`POST /api/v1/credentials/me/rotate-qr`) without mutating issued validity windows.
- **Replacement**: Issuing a new credential automatically marks previous active versions as `REPLACED` and increments version numbers (`v1 -> REPLACED, v2 -> ACTIVE`).
