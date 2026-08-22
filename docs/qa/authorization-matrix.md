# TourSafe QA — Authorization & Access Control Matrix
**Document Version:** 1.0.0  
**Test Suite:** `backend/tests/regression/test_authorization_regression.py`  
**Status:** ✅ **VERIFIED (12/12 Tests Passing)**

---

## 1. Role Definitions & Permissions

TourSafe implements strict Role-Based Access Control (RBAC) supplemented by Attribute-Based Access Control (ABAC) for multi-jurisdiction and tenant isolation.

| Role | Description | Scope of Authority |
| :--- | :--- | :--- |
| **`tourist`** | End-user traveler using the TourSafe mobile application. | Access only to own profile, telemetry sessions, safety status, and consent grants. |
| **`responder`** | Field personnel deployed by authorities for incident response. | Assigned incidents, responder location broadcasting, scene assessments. |
| **`authority`** | Command center dispatchers, police, and emergency services officers. | Jurisdiction-wide incident management, tourist safety history, dispatch orchestration. |
| **`admin`** | System administrators and compliance officers. | Global system configuration, compliance controls, audit exports, legal holds. |

---

## 2. API Endpoint Authorization Matrix

The table below details access permissions across API route groups and verified HTTP response codes.

| Endpoint Category | HTTP Method | Route | `unauthenticated` | `tourist` | `responder` | `authority` | `admin` |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Auth & Identity** | `POST` | `/api/v1/auth/register` | ✅ 201 | ✅ 201 | ✅ 201 | ✅ 201 | ✅ 201 |
| | `POST` | `/api/v1/auth/login` | ✅ 200 | ✅ 200 | ✅ 200 | ✅ 200 | ✅ 200 |
| | `GET` | `/api/v1/auth/me` | ❌ 401 | ✅ 200 | ✅ 200 | ✅ 200 | ✅ 200 |
| **Tourist Domain** | `GET` | `/api/v1/tourists/me` | ❌ 401 | ✅ 200 | ❌ 403 | ❌ 403 | ❌ 403 |
| | `PATCH` | `/api/v1/tourists/me` | ❌ 401 | ✅ 200 | ❌ 403 | ❌ 403 | ❌ 403 |
| | `GET` | `/api/v1/tourists/me/safety` | ❌ 401 | ✅ 200 | ❌ 403 | ❌ 403 | ❌ 403 |
| | `POST` | `/api/v1/tourists/me/sos` | ❌ 401 | ✅ 201 | ❌ 403 | ❌ 403 | ❌ 403 |
| **Authority Domain** | `GET` | `/api/v1/authority/me` | ❌ 401 | ❌ 403 | ❌ 404* | ✅ 200 | ✅ 200 |
| | `GET` | `/api/v1/authority/incidents` | ❌ 401 | ❌ 403 | ❌ 403 | ✅ 200 | ✅ 200 |
| | `GET` | `/api/v1/authority/tourists/{id}/safety` | ❌ 401 | ❌ 403 | ❌ 403 | ✅ 200 | ✅ 200 |
| | `POST` | `/api/v1/authority/incidents/{id}/ack` | ❌ 401 | ❌ 403 | ❌ 403 | ✅ 200 | ✅ 200 |
| | `POST` | `/api/v1/authority/incidents/{id}/resolve`| ❌ 401 | ❌ 403 | ❌ 403 | ✅ 200 | ✅ 200 |
| **Compliance & Privacy** | `GET` | `/api/v1/compliance/controls` | ❌ 401 | ❌ 403 | ❌ 403 | ❌ 403 | ✅ 200 |
| | `POST` | `/api/v1/compliance/legal-holds` | ❌ 401 | ❌ 403 | ❌ 403 | ❌ 403 | ✅ 201 |
| | `POST` | `/api/v1/privacy/consents/grant` | ❌ 401 | ✅ 200 | ❌ 403 | ❌ 403 | ✅ 200 |
| | `POST` | `/api/v1/privacy/consents/withdraw` | ❌ 401 | ✅ 200 | ❌ 403 | ❌ 403 | ✅ 200 |

*\*Note: `responder` role is evaluated in role checks; if profile is unprovisioned, returns 404 instead of 403.*

---

## 3. IDOR (Insecure Direct Object Reference) Protections

TourSafe enforces horizontal privilege boundary controls to prevent unauthorized access between subjects with the same role:

1. **Tourist-to-Tourist Isolation:**
   - Tourist A (`regr_tourist_a`) cannot access Tourist B's (`regr_tourist_b`) safety status, telemetry stream, or incident records.
   - Verified via `test_IDOR_01_tourist_a_cannot_access_tourist_b_safety` and `test_IDOR_02_tourist_a_cannot_access_tourist_b_incidents`.
2. **Tourist-to-Authority Protection:**
   - Tourist cannot acknowledge or resolve incidents belonging to any user.
   - Verified via `test_IDOR_03_tourist_cannot_acknowledge_others_incident`.
3. **Cross-Jurisdiction Isolation:**
   - Authority Alpha (`jurisdiction_alpha`) is strictly forbidden from viewing or modifying incidents assigned to Authority Beta (`jurisdiction_beta`).
   - Verified via `test_XJURIS_01_authority_b_denied_from_authority_a_incident` and `test_XJURIS_02_authority_a_cannot_modify_other_jurisdiction_settings`.

---

## 4. Token Hardening & Bypass Resistance

All endpoints are validated against common bypass attacks:
- **Forged JWT / Invalid Signature:** Rejected with `401 Unauthorized` (`test_SEC_01_forged_token_rejected`).
- **Expired Token:** Rejected with `401 Unauthorized` (`test_SEC_02_expired_token_rejected`).
- **Algorithm None Attack:** Rejected with `401 Unauthorized` (`test_SEC_03_none_algorithm_rejected`).
- **Role Escalation in Claims:** Forged claims in unverified payload fail signature validation (`test_SEC_04_role_escalation_via_forged_token_rejected`).
- **Missing / Empty Auth Headers:** Rejected with `401 Unauthorized` (`test_SEC_BYPASS_01`, `02`, `03`).
