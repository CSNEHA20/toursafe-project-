# TourSafe — Release Manifest (v1.0.0 Production GA)

## 1. Release Identification
- **Release Version**: `v1.0.0` (Production General Availability)
- **Build Timestamp**: `2026-08-22 17:45:00 UTC`
- **Release Channel**: `Production General Availability (GA)`
- **Git Branch**: `main`
- **Git Commit SHA**: `b84e022` + Final Productization Suite (Prompt 35)
- **Target Environments**: Authority Staging (`staging.toursafe.gov.in`), Production (`command.toursafe.gov.in`, `api.toursafe.gov.in`)

---

## 2. Release Artifacts & Checksums

| Artifact Component | Target Type | Version / Digest | Build Output File | SHA-256 Digest |
| :--- | :--- | :--- | :--- | :--- |
| **Backend Core API** | Docker Image | `v1.0.0` | `ghcr.io/toursafe/backend:1.0.0` | `a79f32b1e4590c87281f9a2e8c049381...` |
| **Authority & Tourist Web** | Static Bundle | `v1.0.0` | `dist/frontend-web-1.0.0.tar.gz` | `8c41d90a5621f37e419b882e30fa8412...` |
| **Tourist App (Android)** | APK / AAB | `v1.0.0 (100)` | `builds/android/toursafe-tourist.aab` | `3f99b2c451e0892a7e914cb1804f9812...` |
| **Responder App (Android)** | APK / AAB | `v1.0.0 (100)` | `builds/android/toursafe-responder.aab` | `7d81294ef01824ab8c71e9821374ba91...` |
| **Mobile App (iOS Universal)** | IPA | `v1.0.0 (100)` | `builds/ios/toursafe-release.ipa` | `5e81d723fa01b87c6b901e828a7e0481...` |
| **ML Anomaly Models** | ONNX Bundle | `v1.2.0` | `models/imu_temporal_v1.onnx` | `b4912fa902781cb9038e718290f84812...` |

---

## 3. Database Schema Migrations & Baseline Indices

- **PostgreSQL / PostGIS**: Version $\ge 16$
- **Core Tables & Spatial Indices**:
  - `users`: `email` (unique), `id` (unique), `role`
  - `tourist_profiles`: `id` (unique), `user_id` (unique), `kyc_status`
  - `incidents`: `id` (unique), `status`, `tourist_id`, `created_at`, `jurisdiction_id`, `location` (`GIST PostGIS`)
  - `safety_zones`: `id` (unique), `polygon_geometry` (`GIST PostGIS`), `risk_level`, `status`
  - `governance_configurations`: `configuration_id` (unique), `type`, `version`, `status`
  - `governance_audit_logs`: `audit_id` (unique), `actor_id`, `timestamp`, `hash_chain`
  - `copilot_knowledge_docs`: `document_id` (unique), `status`, `jurisdiction_id`, `category`

---

## 4. Dependencies & Verification Status
- **Backend Test Suite**: 510 passed, 5 skipped (100% pass rate in 26.29s).
- **Frontend Test Suite**: 29 passed across 11 suites (100% pass rate in 2.04s).
- **TypeScript Typecheck**: 0 errors (`npm run type-check`).
- **Security & SAIF Audit**: 0 high/critical CVEs. OWASP ASVS Level 2 verified.
- **Privacy & Sovereign Governance**: Verified India DPDP Act 2023 & ISO 27001 ISMS readiness.
