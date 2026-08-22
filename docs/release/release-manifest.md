# TourSafe — Release Manifest (v1.0.0-rc1)

## 1. Release Identification
- **Release Version**: `v1.0.0-rc1`
- **Build Timestamp**: `2026-08-22 17:16:30 UTC`
- **Release Channel**: `Release Candidate / Production Readiness Verification`
- **Git Branch**: `main`
- **Git Commit SHA**: `b84e022` (Base) + Integration Patches
- **Target Environments**: Staging (`staging.toursafe.io`), Production (`api.toursafe.io`)

---

## 2. Release Artifacts & Checksums

| Artifact Component | Target Type | Version / Digest | Build Output File | SHA-256 Digest |
| :--- | :--- | :--- | :--- | :--- |
| **Backend Core** | Docker Image | `v1.0.0-rc1` | `ghcr.io/toursafe/backend:1.0.0-rc1` | `a79f32b1e4590c87...` |
| **Frontend Web** | Static Bundle | `v1.0.0-rc1` | `dist/frontend-web-1.0.0.tar.gz` | `8c41d90a5621f37e...` |
| **Mobile App (Android)** | APK / AAB | `v1.0.0 (100)` | `builds/android/toursafe-release.aab` | `3f99b2c451e0892a...` |
| **Mobile App (iOS)** | IPA | `v1.0.0 (100)` | `builds/ios/toursafe-release.ipa` | `5e81d723fa01b87c...` |
| **ML Inference Models** | ONNX Bundle | `v1.2.0` | `models/imu_temporal_v1.onnx` | `b4912fa902781cb9...` |

---

## 3. Database Schema Migrations & Baseline Indices

- **MongoDB Version Requirement**: $\ge 7.0$
- **Collections & Indexes**:
  - `users`: `email` (unique), `id` (unique), `role`
  - `tourists`: `id` (unique), `user_id` (unique), `kyc_status`
  - `incidents`: `id` (unique), `status`, `tourist_id`, `created_at`, `jurisdiction_id`, `location` (`2dsphere`)
  - `zones`: `id` (unique), `boundary` (`2dsphere`), `center` (`2dsphere`), `status`, `risk_level`
  - `governance_configurations`: `configuration_id` (unique), `type`, `version`, `status`
  - `governance_audit_logs`: `audit_id` (unique), `actor_id`, `timestamp`, `hash_chain`
  - `copilot_knowledge_docs`: `document_id` (unique), `status`, `jurisdiction_id`, `category`

---

## 4. Dependencies & Security Audit
- **Python Dependencies**: 0 high/critical CVEs. Locked via `requirements.txt`.
- **Node.js Dependencies**: 0 high/critical vulnerabilities via `npm audit`.
- **Static Code Analysis**: All 515 test cases passing (100% test success rate).
- **Compliance Certification**: Verified SAIF compliance, GDPR/DPDP data minimization filters active.
