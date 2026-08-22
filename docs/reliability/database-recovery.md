# TourSafe Database Disaster Recovery Runbook

## 1. Failure Scenarios & Architecture Context
- **Current Architecture**: Single-node or primary replica MongoDB deployment.
- **Risks**: Primary replica network partition, disk full, corrupted document index, transient socket timeouts.

---

## 2. Recovery Procedures

### Scenario A: Transient Primary Network Drop
1. Ingress requests automatically retry with exponential backoff via `with_db_retry`.
2. Write operations are guarded by `idempotent_write_guard` to prevent duplicate SOS records.
3. If partition exceeds 30s, the system switches to `CRITICAL_ONLY` mode.

### Scenario B: Data Corruption or Catastrophic Node Loss
1. **Isolate Traffic**: Direct load balancer to display maintenance page or switch to offline buffering.
2. **Inspect Latest Snapshot**:
   ```bash
   ls -la /backups/
   ```
3. **Verify Archive Checksum**:
   ```bash
   sha256sum /backups/bkp_latest.json.gz
   ```
4. **Execute Restore Service**:
   ```bash
   python -c "
   import asyncio
   from app.services.reliability.restore_service import restore_service
   asyncio.run(restore_service.restore_from_backup('bkp_latest', dry_run=False))
   "
   ```
5. **Verify Indexes**:
   On application startup, `lifespan` automatically runs `init_db_indexes()` to regenerate 2dsphere and unique indexes.
