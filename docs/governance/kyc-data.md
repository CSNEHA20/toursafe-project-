# TourSafe Identity & KYC Data Governance

**Scope:** Identity Verification, KYC Documents, and Digital Tourist Credentials (TSQR)  

---

## 1. Document Collection & Verification Flow

1. **Document Types Supported:** Passport, National Identity Card, Aadhaar Card, Driving License.
2. **OCR Extraction:** Extracts only essential verification fields (`full_name`, `date_of_birth`, `nationality`, `document_number`).
3. **Storage Security:** Raw identity document images are stored with server-side AES-256 encryption. Access is restricted to authorized KYC review personnel.
4. **Digital Credential Generation:** Issues a tamper-evident TSQR code containing an HMAC-SHA256 signature and cryptographic public key verification token.

---

## 2. Retention & Deletion Policy

* **Verified Profile Metadata:** Retained for the duration of the tourist trip + 365 days post-departure to support tourism authority security audits.
* **Unverified / Draft KYC Submissions:** Automatically purged after 30 days of inactivity.
* **Data Subject Erasure (DSR):** Upon verified identity verification, non-incident KYC records are permanently deleted, and the user profile is pseudonymized (`[DELETED_USER]`).
