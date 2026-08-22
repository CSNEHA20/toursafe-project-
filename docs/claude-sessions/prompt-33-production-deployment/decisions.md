# TourSafe Prompt 33 — Architectural Decisions

## Decision 1: Non-Root Container Security Boundary
- **Context**: Standard Docker images running as UID 0 (root) present security risks in multi-tenant or container breakout scenarios.
- **Decision**: All production Dockerfiles (`backend/Dockerfile`, `Dockerfile.worker`, `Dockerfile.ml`) define and run strictly as system non-root user `toursafe:toursafe` (UID 10001). Kubernetes `securityContext` explicitly enforces `runAsNonRoot: true`.

## Decision 2: Hardened Startup Environment Validation
- **Context**: Deploying to production with default development secrets (e.g. `JWT_SECRET`, wildcard `*` CORS) creates severe vulnerabilities.
- **Decision**: Added Pydantic model validator in `backend/app/core/config.py` that fails fast during startup if `ENVIRONMENT=production` and any weak/default keys or wildcard CORS headers are present.

## Decision 3: Synthetic Guard for Smoke Tests
- **Context**: Post-deployment smoke tests must validate emergency incident state progression without triggering real sirens, SMS, or dispatching real emergency responders.
- **Decision**: Added explicit `is_synthetic: true` and `suppress_external_dispatch: true` flags to all synthetic smoke test pipelines.

## Decision 4: Zero-Trust Database & Redis Network Isolation
- **Context**: MongoDB and Redis instances must never be exposed to public ingress.
- **Decision**: In Docker Compose, MongoDB and Redis bind to internal bridge network `data_net: internal: true`. In Kubernetes, `NetworkPolicies` enforce default-deny and permit traffic only from authenticated API and worker pods.

## Decision 5: Versioned Schema Migration Engine
- **Context**: MongoDB schema evolution requires traceable, reversible, and auditable forward progress.
- **Decision**: Implemented `MigrationEngine` in `backend/app/core/migrations.py` storing execution status and checksums in `_schema_migrations` collection with forward, rollback, and dry-run capabilities.
