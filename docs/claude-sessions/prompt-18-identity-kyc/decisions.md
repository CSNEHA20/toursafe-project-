# Architectural Decisions: Prompt 18 — Identity, KYC & Digital Tourist Credential

## Decision 1: Separation of Identity Domain from User Account and Safety State
- **Reason**: The User Account manages credentials and authentication (JWT). The Tourist Identity Profile manages verified identity metadata. Safety operations (geofences, LSTM anomalies, incidents) manage real-time operational state. Combining them violates data minimization and creates dangerous coupling where a verified identity might be mistakenly treated as incident-free or trusted.
- **Alternatives**: Store all KYC and credential fields directly on `User` or `Tourist` models.
- **Why Selected**: Ensures independent lifecycle management, prevents privilege escalation, and enforces strict boundary isolation.

---

## Decision 2: Zero Trust/Risk Scoring Charter
- **Reason**: Prompt 18 strictly mandates that KYC only answers *"Has this identity/profile been verified according to the configured verification process?"* It must never create behavioral trust scores, risk scores, or social rankings.
- **Alternatives**: Compute a "Trust Index" based on verified documents + trip history.
- **Why Selected**: Rejected because trust scoring introduces severe privacy violations, algorithmic bias, demographic discrimination, and false safety illusions.

---

## Decision 3: Explicit DEV_KYC_PROVIDER Labeling
- **Reason**: Real third-party KYC providers require live contract credentials and legal compliance. In development and testing, simulated providers must be unambiguously labeled so operators and tourists never mistake simulated test data for legal government-backed verification.
- **Alternatives**: Fake a production provider name (e.g., claiming "Veriff Verified").
- **Why Selected**: Unambiguous labeling (`DEV_KYC_PROVIDER`, `is_real_provider = False`) complies with ethical AI and security standards.

---

## Decision 4: Opaque Signed QR Payloads (TSQR) with Replay-Resistant Nonces
- **Reason**: Storing raw user IDs, national ID numbers, or full profile data in QR codes exposes sensitive PII to anyone scanning the code.
- **Alternatives**: Plaintext JSON containing user name, DOB, and passport number in the QR code.
- **Why Selected**: Using HMAC-SHA256 over opaque references with rotating token nonces (`TSQR:...`) enables instant offline and online verification without leaking personal information.

---

## Decision 5: Credential Replacement Policy (v1 -> REPLACED, v2 -> ACTIVE)
- **Reason**: Issued credentials should be immutable snapshots. If identity details change or a renewal occurs, mutating existing credentials destroys auditability.
- **Alternatives**: Mutate the existing credential record in-place.
- **Why Selected**: Incrementing version numbers and marking previous credentials as `REPLACED` ensures that an old printed QR code or stolen token immediately verifies as `INVALID`.
