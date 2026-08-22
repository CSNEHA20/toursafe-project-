# Problems Encountered & Solutions Applied — Prompt 30

## Problems & Solutions

### 1. Test Environment MongoDB Socket Connection Timeouts
- **Problem**: When running pytest without a standalone MongoDB daemon on localhost:27017, direct Motor driver calls hung for 30s before throwing `ServerSelectionTimeoutError`.
- **Solution**: Implemented an async `MockDB` / `MockCollection` fixture and dynamic `db_core.get_database()` bindings across `backup_service`, `restore_service`, `incident_timeline`, and `queue_resilience`.

### 2. Snapshot Backup ID Collisions in Rapid Unit Tests
- **Problem**: In unit tests executing within the same second, `backup_id` generated with format `bkp_%Y%m%d_%H%M%S` created identical IDs, leading to checksum verification looking up the prior backup archive.
- **Solution**: Appended a 6-character UUID hex snippet (`bkp_%Y%m%d_%H%M%S_<hex>`) guaranteeing global uniqueness across milliseconds.

### 3. JSX Parsing Error in React Native Web Text Node
- **Problem**: `ReliabilityDashboard.tsx` had raw `>100ms` inside a JSX `<Text>` node, causing a TypeScript parser error (`TS1382: Unexpected token. Did you mean {'>'} or &gt;?`).
- **Solution**: Escaped the character using `(&gt;100ms)`.

### 4. Circular Import in Health & Reliability Routers
- **Problem**: `get_current_user` was initially imported from `app.core.security` instead of `app.routers.auth`, causing an import error during test discovery.
- **Solution**: Fixed imports to `from .auth import get_current_user`.
