# TourSafe CI/CD Pipelines & Release Engineering

## Continuous Integration Pipeline (`.github/workflows/ci.yml`)

The CI workflow runs on every pull request and push to `main`:

```
+-----------------------------------------------------------------------------------+
|                              TourSafe CI Pipeline                                 |
+-----------------------------------------------------------------------------------+
|  [Secret Scan]       -> Gitleaks checks for exposed credentials, JWT keys, tokens |
|  [Lint & Typecheck]  -> ESLint, TypeScript (tsc --noEmit), Python formatting check |
|  [Backend Regression]-> Pytest Security, Reliability, Governance, QA Regression   |
|  [E2E Lifecycle]     -> Golden Path E2E verification with mock fixtures           |
+-----------------------------------------------------------------------------------+
```

---

## Continuous Delivery Pipeline (`.github/workflows/cd.yml`)

The CD workflow triggers upon semantic version tagging (`v*.*.*`) or manual promotion dispatch:

1. **Stage 1: Multi-Stage Container Build & Scan**:
   - Compiles non-root Docker images for `backend-api`, `worker`, `ml-service`, and `frontend-web`.
   - Tags images with immutable Git commit SHA and SemVer (`ghcr.io/toursafe/backend-api:v1.0.0`, `:a1b2c3d`).
   - Trivy container security scanning checks for zero critical/high CVEs.
   - Syft generates Software Bill of Materials (SBOM) in SPDX format.
2. **Stage 2: Staging Deployment & Automated Validation**:
   - Executes non-destructive schema migrations forward via `python scripts/migrate.py up`.
   - Deploys Kubernetes staging manifests.
   - Runs post-deployment synthetic smoke test (`python scripts/synthetic_smoke_test.py`).
3. **Stage 3: Production Deployment (Approval Gate)**:
   - Requires explicit authorized approval from DevOps / Lead Engineer.
   - Executes pre-deployment database backup snapshot drill.
   - Performs Kubernetes zero-downtime rolling update (`maxUnavailable: 0`, `maxSurge: 1`).
   - Executes final post-deployment synthetic smoke test.

---

## Rollback Workflow (`.github/workflows/rollback.yml`)

Automated and manual rollback mechanism:
- Invoked via manual GitHub Action dispatch or automated alert webhook on high error rates / SLO breach.
- Executes `kubectl rollout undo deployment/toursafe-api -n toursafe`.
- Verifies post-rollback health status.
