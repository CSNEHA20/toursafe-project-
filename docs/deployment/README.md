# TourSafe Production Deployment & Infrastructure Documentation

Welcome to the comprehensive DevOps, CI/CD, and Infrastructure engineering documentation for the TourSafe platform.

## Documentation Index

1. [Service Inventory](file:///docs/deployment/service-inventory.md) — Comprehensive inventory of all services, ports, runtimes, dependencies, and health probes.
2. [Production Architecture](file:///docs/deployment/production-architecture.md) — Network topology, data flow, VPC subnet isolation, and zero-trust security boundaries.
3. [Environment Matrix](file:///docs/deployment/environment-matrix.md) — Specification and environment parity across dev, test, staging, and production.
4. [Infrastructure Specifications](file:///docs/deployment/infrastructure.md) — DNS, domain configurations, database connection pools, Redis policies, and secrets management.
5. [CI/CD Pipelines](file:///docs/deployment/cicd.md) — GitHub Actions workflows for continuous integration, multi-stage container delivery, vulnerability scanning, and rollback.
6. [Production Release Checklist](file:///docs/deployment/production-release-checklist.md) — Step-by-step gate verification checklist for production promotions.
7. [Production Runbook](file:///docs/deployment/production-runbook.md) — Operational procedures for system startup, health monitoring, metrics, and incident triage.
8. [Disaster Recovery Runbook](file:///docs/deployment/disaster-recovery-runbook.md) — Backup snapshot procedures, restoration drills, and RTO/RPO targets.
9. [Capacity & Cost Model](file:///docs/deployment/cost-and-capacity-model.md) — Throughput estimations, resource sizing, and cost optimization levers.
10. [Mobile Build Pipeline](file:///docs/deployment/mobile-build-pipeline.md) — Expo EAS build profiles, Android AAB / iOS IPA packaging, and client secret security.

---

## Quick Reference CLI Commands

```bash
# Check Schema Migration Status
python scripts/migrate.py status

# Run Forward Database Migrations
python scripts/migrate.py up

# Execute Post-Deployment Synthetic Smoke Test
python scripts/synthetic_smoke_test.py

# Run Disaster Recovery Backup & Restoration Drill
python scripts/backup_restore_drill.py

# Bootstrap Root Authority Administrator
python scripts/bootstrap_admin.py --email admin@toursafe.internal
```
