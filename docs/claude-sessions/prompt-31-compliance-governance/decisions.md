# Architectural Decisions — Prompt 31

## 1. Compliance Readiness vs False Certification
- **Decision:** Explicitly mark all framework evaluations as "Readiness Assessments" with a mandatory disclaimer on reports: *"Technical readiness assessment only; not legal certification."*
- **Rationale:** Regulatory compliance under GDPR, India DPDP, ISO 27001, and SOC 2 requires formal third-party audits and legal counsel assessments. Claiming automated compliance would create legal and compliance liabilities.

## 2. Granular Unbundled Consent & Vital Interests Exception
- **Decision:** Decouple core safety permissions (GPS geofencing, emergency SMS) from optional processing (anonymous analytics, AI personalization).
- **Rationale:** Avoids dark patterns and bundle coercion. During an active SOS alarm or severe incident, data processing continues under the statutory basis of `VITAL_INTERESTS_EMERGENCY` without violating tourist consent policy.

## 3. Safe Deletion & Legal Hold Precedence
- **Decision:** Any automated retention sweep or DSR erasure request MUST verify whether the target entity is under an active `LEGAL_HOLD` or involved in an ongoing emergency incident.
- **Rationale:** Prevents catastrophic destruction of critical evidence during court investigations or search-and-rescue operations.

## 4. Multi-Jurisdiction Server-Side Resolution
- **Decision:** Resolve retention and data governance policies server-side by checking the specific authority jurisdiction before falling back to global baseline policies.
- **Rationale:** Eliminates frontend tampering and accommodates regional statutory differences (e.g. EU GDPR vs India DPDP).
