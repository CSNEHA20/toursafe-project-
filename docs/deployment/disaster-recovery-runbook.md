# TourSafe Disaster Recovery Runbook & Backup Strategy

## Disaster Recovery Objectives (SLO / SLA)

- **Recovery Point Objective (RPO)**: **< 1 minute** (Continuous AOF + hourly incremental DB snapshots).
- **Recovery Time Objective (RTO)**: **< 5 minutes** (Automated replica failover and rapid snapshot restoration).

---

## Backup Architecture

1. **MongoDB Primary Snapshots**:
   - Hourly incremental and daily full snapshots compressed via gzip and encrypted with AWS KMS AES-256.
   - Uploaded directly to private S3 bucket `toursafe-backups-production`.
   - Retention policy: 90 days with Glacier transition after 30 days.
2. **Redis In-Memory Persistence**:
   - Hybrid snapshotting (`RDB` every 5 minutes + `AOF` with `appendfsync everysec`).
   - Volatile keys (live telemetry caches) expire automatically via TTL (120s), while active state snapshots persist to volume.
3. **KYC Vault S3 Bucket**:
   - Cross-Region Replication (CRR) enabled between primary region (`us-east-1`) and secondary disaster recovery region (`us-west-2`).
   - Versioning and Object Lock (Compliance mode) enabled to protect against accidental deletion.

---

## Restoration Procedure & Recovery Drill

To execute a full database restore from an S3 backup snapshot:

```bash
# 1. Download target snapshot from encrypted backup vault
aws s3 cp s3://toursafe-backups-production/mongodb/snap_20260822_000000.json.gz ./backend/backups/

# 2. Run automated restoration and integrity verification script
python scripts/backup_restore_drill.py

# 3. Apply pending migrations to reconcile schema version
python scripts/migrate.py up

# 4. Verify system health and run synthetic smoke test
python scripts/synthetic_smoke_test.py
```

---

## Disaster Recovery Drill Schedule
- **Weekly Automated Drill**: GitHub Actions workflow `.github/workflows/db-backup-restore-drill.yml` executes every Sunday at 02:00 UTC.
- **Bi-Annual Regional Failover Simulation**: Operations team simulates primary region outage and validates traffic redirect to secondary warm standby.
