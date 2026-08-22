# TourSafe STRIDE Threat Model & Defense-in-Depth Analysis

## 1. Attacker Models
TourSafe evaluates threats across 10 distinct attacker profiles:
1. **Unauthenticated Public Attacker**: Exploits exposed API endpoints, attempts brute-force credential stuffing, password guessing, or NoSQL injection.
2. **Malicious Authenticated Tourist**: Attempts IDOR on other tourists' GPS tracks, tampers with client-side telemetry sequence numbers, or attempts SOS spamming.
3. **Compromised Field Responder**: Attempts unauthorized access to other jurisdictions or sensitive tourist KYC data outside their assigned incident.
4. **Rogue / Compromised Authority Operator**: Tries to tamper with historical incident audit trails, elevate privileges, or view records in unassigned jurisdictions.
5. **Malicious Administrator**: Attempts unauthorized policy deployments without peer approval or rollback verification.
6. **Lost / Stolen Mobile Device**: Attempts session reuse, cached credential extraction, or offline token replay.
7. **Malicious External Webhook Source**: Spoofs event notifications, replays old disaster alerts, or attempts payload-based XSS/injection.
8. **SSRF Exploiter**: Attempts to abuse outbound integration webhooks to access internal VPC resources (10.0.0.0/8, 127.0.0.1, AWS/GCP metadata `169.254.169.254`).
9. **LLM Prompt Injection Attacker**: Injects adversarial instructions into tourist emergency descriptions or OCR documents to trigger unauthorized AI tool execution.
10. **Telemetry Flooder / Replay Attacker**: Replays stale GPS or high-frequency IMU packets to overwhelm ingestion pipelines or simulate false incidents.

---

## 2. STRIDE Threat Analysis Matrix

| Threat Category | Asset / Surface | Threat Scenario | Impact | Likelihood | Implemented Mitigation | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Spoofing (S)** | Mobile GPS Telemetry | Attacker transmits simulated/mock GPS coordinates across country | High | Medium | `validate_gps_sample` kinematic velocity check (>350 m/s threshold) + Mock Location flag rejection | **MITIGATED** |
| **Spoofing (S)** | Outbound Webhook Integrations | Malicious third party sends fake dispatch status updates | High | Medium | HMAC-SHA256 signature verification + event timestamp freshness window (5 min) | **MITIGATED** |
| **Tampering (T)** | Governance Audit Log | Compromised admin modifies past audit logs to conceal unauthorized actions | Critical | Low | SHA-256 Cryptographic Hash Chaining (`previous_hash` + payload checksum) + immutable database guards | **MITIGATED** |
| **Tampering (T)** | Telemetry Stream | Replay of old accelerometer/gyroscope packets to trigger false anomaly alerts | Medium | Medium | Strict sequence number monotonicity check (`validate_telemetry_sequence_and_replay`) + session binding | **MITIGATED** |
| **Repudiation (R)** | Emergency Response Actions | Dispatcher claims they never resolved/closed an incident | High | Low | Immutable audit logging of all incident state transitions with actor ID, timestamp, and client IP | **MITIGATED** |
| **Information Disclosure (I)**| API Endpoints (IDOR) | Tourist A calls `/api/v1/tourists/me/location` vs attempting `/tourists/{B}/location` | High | High | Strict JWT-derived tourist resolution; path-based IDOR rejected by ABAC ownership checks | **MITIGATED** |
| **Information Disclosure (I)**| Application Logs | Passwords, JWT tokens, KYC, or exact GPS coordinates leaked to stdout/log aggregators | High | Medium | `sanitize_pii_for_logs` redacting tokens, passwords, emails, and phone numbers before logging | **MITIGATED** |
| **Denial of Service (D)**| Auth / Login Endpoints | Brute force credential stuffing or massive registration flood | High | High | Sliding-window `auth_rate_limiter` and `registration_rate_limiter` with progressive Retry-After headers | **MITIGATED** |
| **Denial of Service (D)**| Emergency SOS Pipeline | Attacker sends rapid SOS requests to exhaust responders | Critical | Medium | Safety-aware deduplication (`check_sos_rate_and_deduplicate`): preserves dispatch while correlating rapid duplicates | **MITIGATED** |
| **Elevation of Privilege (E)**| RBAC & Role Transition | Tourist token used to call Authority Admin configuration endpoints | Critical | High | Role-based dependency verification (`require_role`), token claim integrity, and strict separation of duties | **MITIGATED** |
| **Elevation of Privilege (E)**| AI Copilot Engine | Prompt injection in incident note tricks Copilot into executing unauthorized tools | Critical | Medium | Copilot tool permissions filter + Two-Phase Verification Action Tokens with explicit user confirmation | **MITIGATED** |
| **Elevation of Privilege (E)**| External Adapters (SSRF)| Outbound webhook URL points to `http://169.254.169.254/latest/meta-data` | Critical | Medium | Outbound SSRF validator (`validate_outbound_url`) blocking private, loopback, and metadata IP spaces | **MITIGATED** |
