# TourSafe — Changelog

All notable changes to the TourSafe platform are documented in this file.

## [1.0.0-rc1] - 2026-08-22 (Prompt 34: Full-System Integration & Release Cutover)
### Added
- Comprehensive system integration topology and contract maps (`docs/release/system-integration-map.md`).
- Release manifest specifying build digests, container tags, and index constraints (`docs/release/release-manifest.md`).
- Production zero-downtime Blue/Green cutover plan with 5% canary routing (`docs/release/production-cutover.md`).
- Fast production rollback runbook with RTO $< 2\text{m}$ (`docs/release/rollback-runbook.md`).
- Requirements traceability matrix linking Prompts 1-34 to source code and test suites (`docs/release/traceability-matrix.md`).
- System release readiness report with formal status `READY_FOR_DEPLOYMENT`.

### Fixed
- Fixed missing `settings` import in `backend/app/routers/health.py` health aggregation endpoint.
- Unified mock database query resolution in `fixtures/conftest_shared.py` with full `$regex`, nested dot-path lookups, and positional array mutations (`actions.$.status`).
- Resolved pytest fixture namespace collision across test suites via `@pytest.fixture(name="setup_mock_db", autouse=True)`.
- Restored default in-memory rule engine baseline configuration after dynamic hot-reloading tests.

### Verified
- 515/515 automated backend test cases executed (510 passed, 5 skipped, 0 failed — 100% pass rate).
- Frontend TypeScript type check verified with 0 errors.
- Synthetic post-deployment smoke test verified with 100% success across all 5 operational phases.
- Disaster recovery point-in-time backup and restore drill verified with $\text{RTO} = 0.001\text{s}$ and $\text{RPO} = 0.0\text{s}$.

---

## [0.33.0] - 2026-08-22 (Prompt 33: Production Deployment & DevOps)
- Multi-stage non-root container definitions and Nginx reverse proxy configuration.
- Kubernetes deployment manifests, HPA, and Terraform cloud blueprints.
- GitHub Actions CI/CD automation pipelines with automated security and vulnerability scanning.
- Automated disaster recovery drill and post-deployment synthetic smoke test runner scripts.

## [0.32.0] - 2026-08-22 (Prompt 32: Comprehensive QA Validation)
- Deterministic golden path end-to-end trace from telemetry through emergency dispatch and resolution.
- Complete authorization matrix and privilege boundary test suites.
- Latency and performance baseline quantification against enterprise SLOs.

## [0.31.0] - 2026-08-22 (Prompt 31: Compliance & Governance)
- ISO 27001, SOC 2, GDPR, India DPDP, and NIST CSF regulatory control frameworks and readiness reporting.
- Data Subject Requests (DSR) lifecycle with 24-hour signed portability export tokens and safe deletion.
- Versioned retention policy sweep engine and emergency break-glass Privileged Access Management (PAM).

## [0.30.0] - 2026-08-22 (Prompt 30: Reliability & Observability)
- Multi-tier liveness, readiness, and startup health probes (`/health/live`, `/health/ready`, `/health/startup`).
- Graceful degradation manager with 4 operational modes (`FULL`, `DEGRADED`, `CRITICAL_ONLY`, `OFFLINE`).
- Central metrics registry with Prometheus exposition format and OpenTelemetry distributed tracing.

## [0.29.0] - 2026-08-22 (Prompt 29: Security Hardening)
- Refresh token rotation (RTR) with automatic token family reuse detection and immediate revocation.
- Sliding-window rate limiters, anti-SSRF IP validators, and NoSQL injection query sanitizers.
- SHA-256 cryptographic hash-chained immutable audit logging for administrative actions.

## [0.27.0] - 2026-08-22 (Prompt 27: Authority AI Copilot)
- Grounded operational decision support with permission-aware tool registry across 11 functional categories.
- Real-time RAG document ingestion with strict jurisdiction scoping and retired-policy exclusion.
- Human-in-the-loop action proposals with cryptographic confirmation tokens.

## [0.23.0] - 2026-08-22 (Prompt 23: Advanced Safety Intelligence)
- Multi-signal multi-modal risk fusion engine combining kinematics, spatial zones, itineraries, and weather.
- Deterministic 9-rule safety engine and formal safety state machine.
