# TourSafe — Production Migration Plan

## 1. Scope & Objective
This migration plan outlines the forward data migration, collection restructuring, geospatial index verification, and state initialization required to transition staging and legacy data environments to **TourSafe v1.0.0-rc1**.

---

## 2. Pre-Migration Checklist
- [x] Full point-in-time snapshot backup generated and verified with `scripts/backup_restore_drill.py`.
- [x] Database replication lag verified $< 1.0\text{s}$ across all replica set nodes.
- [x] Migration dry-run executed in isolated staging namespace with 0 schema validation errors.
- [x] Maintenance window scheduled with emergency CAD and notification fallbacks standby.

---

## 3. Migration Sequence & Steps

### Step 1: Baseline Collection & Index Creation
Run automated initialization to ensure 2dsphere and unique constraints exist:
```bash
python -c "import asyncio; from app.core.database import init_db_indexes; asyncio.run(init_db_indexes())"
```

### Step 2: Configuration & Policy Governance Seeding
Seed baseline versioned governance configurations and active response policies:
```bash
python -c "import asyncio; from app.services.authority.config_governance_service import config_governance_service; asyncio.run(config_governance_service.init_defaults())"
```

### Step 3: Copilot Knowledge Base & RAG Seeding
Seed default standard operating procedures, SLAs, and emergency policy manuals:
```bash
python -c "import asyncio; from app.services.copilot.rag_service import rag_service; asyncio.run(rag_service.init_indexes())"
```

### Step 4: Verification of Data Integrity
Execute schema integrity validation across all collections:
- Verify `users` documents contain valid `id`, `email`, `role`, and `hashed_password`.
- Verify `incidents` documents contain valid `incident_id`, `status`, `timeline`, and `version`.
- Verify `zones` documents contain valid GeoJSON Polygons with clockwise coordinates.

---

## 4. Post-Migration Validation
Execute the post-deployment synthetic smoke test to confirm end-to-end signal processing, incident creation, responder dispatch, and resolution:
```bash
python scripts/synthetic_smoke_test.py
```
Expected output: `ALL SYNTHETIC SMOKE TEST PHASES PASSED (100% SUCCESS)`.
