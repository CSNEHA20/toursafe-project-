# TourSafe Backup & Restoration Runbook

## 1. Backup Strategy, Frequency & Retention

| Backup Tier | Frequency | Target / Content | Storage Location | Retention Period | RPO Target |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **System Snapshot (Full)** | Every 6 Hours | All collections (incidents, users, zones, policies, audit_logs) | Encrypted Gzip JSON archive (`/backups/`) | 7 Days Rolling | **6 Hours** (Snapshots) |
| **Emergency Audit Export** | Daily 00:00 UTC | Security events, audit_logs, compliance chains | Encrypted Cold Storage | 365 Days | **24 Hours** |
| **Incremental Write Log** | Continuous (Replica) | MongoDB Oplog / Change Streams | Replica secondary nodes | 48 Hours | **< 15 Minutes** |

### Encryption & Integrity
- All backup archives are compressed and hashed with **SHA-256**.
- Checksums are verified before storing and immediately before any restoration attempt.
- Archives are encrypted at rest using AES-256.

---

## 2. Realistic RPO & RTO Parameters

> [!NOTE]
> - **RPO (Recovery Point Objective)**: **15 Minutes** (Maximum acceptable data loss window during catastrophic crash).
> - **RTO (Recovery Time Objective)**: **Target < 15 Minutes** for full collection restore; **< 5 Minutes** for application service recovery.

---

## 3. Restoration Procedure (Step-by-Step)

### Step 1: Inspect Available Backups
```bash
curl -X GET https://api.toursafe.io/api/v1/reliability/backups \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

### Step 2: Execute Dry-Run Restoration
Always perform a dry-run first to verify archive checksums and validate schema compatibility without modifying database state:
```bash
curl -X POST https://api.toursafe.io/api/v1/reliability/backups/restore \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"backup_id": "bkp_20260822_120000", "dry_run": true}'
```

### Step 3: Execute Production Database Restore
```bash
curl -X POST https://api.toursafe.io/api/v1/reliability/backups/restore \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"backup_id": "bkp_20260822_120000", "dry_run": false}'
```

### Step 4: Post-Restore Verification Checklist
1. **Health Verification**: Check `/health/ready` returns `status: HEALTHY`.
2. **Collection Counts**: Verify `incidents`, `users`, and `geospatial_zones` record counts match backup metadata.
3. **Consistency Check**: Verify active responder units reconcile with their assigned open incidents.
4. **Idempotency Guard**: Ensure duplicate events are ignored upon client reconnection.
