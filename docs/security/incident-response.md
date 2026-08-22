# TourSafe Security Incident Response Plan (SIRP)

## 1. Incident Severity Levels

| Level | Severity Name | Description | Response Time SLA | Escalation Target |
| :--- | :--- | :--- | :--- | :--- |
| **SEV-1** | **CRITICAL** | Active data breach, refresh token family reuse compromise, unauthorized administrative policy modification, or audit tampering detection. | < 15 minutes | Security Incident Lead, CTO, Emergency Ops Lead |
| **SEV-2** | **HIGH** | Outbound SSRF attempt blocked, repeated brute-force authentication attacks, or AI Copilot prompt injection attempts. | < 1 hour | Security Engineering Team |
| **SEV-3** | **MEDIUM** | Single user suspicious login, unusual GPS kinematic anomaly, or localized rate-limit violation. | < 4 hours | On-call Security Analyst |
| **SEV-4** | **LOW** | Minor dependency vulnerability alert or non-critical formatting anomaly. | < 24 hours | Development Team |

---

## 2. Response Workflows

### Scenario A: Compromised User or Admin Session
1. **Detection**: User reports unauthorized activity or RTR engine flags token reuse (`auth.token.reuse_detected`).
2. **Containment**: Execute `/api/v1/admin/security/tokens/revoke` to blacklist the token JTI and terminate the session family.
3. **Eradication**: Force password reset using Argon2id with mandatory elevated verification.
4. **Recovery & Post-Mortem**: Verify audit chain integrity using `/api/v1/admin/security/audit/verify` to confirm no unauthorized changes occurred during the session window.

### Scenario B: Suspected Audit Tampering
1. **Detection**: Integrity verification endpoint `/api/v1/admin/security/audit/verify` returns `valid: false` with broken hash chain.
2. **Containment**: Isolate affected administrative accounts; place governance subsystem into read-only maintenance mode.
3. **Investigation**: Inspect `security_events` and database replica logs to identify point of unauthorized database manipulation.
4. **Remediation**: Restore verified state from encrypted, immutable backup snapshots and re-verify cryptographic hash chain.
