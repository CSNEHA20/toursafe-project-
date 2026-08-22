# TourSafe Production Release Checklist

Before promoting any release build to the production environment, all steps must be verified and signed off.

## Phase 1: Pre-Release Verification
- [ ] **CI Pipeline Green**: All 45+ regression tests (Security, Reliability, Governance, QA, E2E) passed without failure.
- [ ] **Secret Scan Clean**: Gitleaks reports zero unencrypted secrets in commit history.
- [ ] **Container Vulnerability Scan**: Trivy reports zero Critical or High CVEs in base images.
- [ ] **SBOM Generated**: SPDX / CycloneDX bill of materials generated for audit compliance.
- [ ] **Staging Soak Completed**: Release candidate tested on staging cluster with synthetic smoke test.

## Phase 2: Deployment Preparation
- [ ] **Database Pre-flight Snapshot**: Run `python scripts/backup_restore_drill.py` or trigger managed cloud backup.
- [ ] **Schema Migrations Review**: Verify all forward migrations are backward-compatible (`python scripts/migrate.py status`).
- [ ] **Secrets Injected**: Confirm production JWT keys, database credentials, and API tokens are active in Secrets Manager.
- [ ] **Change Advisory Sign-Off**: Release approved by designated Operations / Engineering lead.

## Phase 3: Rollout Execution
- [ ] **Initiate Zero-Downtime Rolling Update**: Deploy new image tags via Kubernetes / Docker Compose.
- [ ] **Monitor Deployment Pods**: Verify all new replicas transition to `Running` and pass readiness probes (`/health/ready`).
- [ ] **WebSocket Connection Drain**: Confirm existing WebSocket connections drain gracefully without dropped messages.

## Phase 4: Post-Deployment Validation
- [ ] **Health Endpoint Check**: Verify `GET /health` returns `status: healthy` with correct `app_version` and `build_sha`.
- [ ] **Execute Synthetic Smoke Test**: Run `python scripts/synthetic_smoke_test.py` and confirm 100% pass rate.
- [ ] **Metrics & Golden Signals**: Monitor Grafana dashboards for latency spikes, error rate (< 0.1%), and memory utilization.
- [ ] **Release Notes Published**: Release tag and changelog documented in repository.
