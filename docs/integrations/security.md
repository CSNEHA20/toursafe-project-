# Integration Security & Threat Protection

## 1. SSRF (Server-Side Request Forgery) Defense

To prevent malicious operators or manipulated payload URLs from pivoting into internal infrastructure or cloud metadata services:
- **Blocked IP Networks**:
  - `127.0.0.0/8` (Loopback)
  - `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` (Private RFC1918)
  - `169.254.0.0/16` (Cloud Metadata / Link-Local, e.g. AWS/GCP `169.254.169.254`)
  - `::1/128`, `fe80::/10` (IPv6 loopback & link-local)
- **Domain Allowlisting**: Outbound requests validate against configured allowlists (e.g. `api.openstreetmap.org`, `maps.googleapis.com`, `api.twilio.com`).

---

## 2. Secret Redaction & Protection

- API keys, Bearer tokens, private certificates, and client secrets are recursively redacted via regex pattern matching (`api_key`, `secret`, `token`, `password`, `bearer`).
- Masks secrets to `sk_l****cdef` or `********` across all:
  - REST API responses
  - Console / Log output
  - Audit trail logs
  - Frontend admin screens (displayed simply as `CONFIGURED` or `NOT CONFIGURED`)
  - AI Copilot context tools

---

## 3. PII Minimization

- External dispatches to non-emergency partners (weather, tourism, analytics) automatically fuzz GPS coordinates to 3 decimal places (~100m radius).
- Phone numbers are masked (e.g. `+91 98****10`).
- Sensitive medical records (blood group, allergies, conditions) are automatically purged from third-party payloads.
