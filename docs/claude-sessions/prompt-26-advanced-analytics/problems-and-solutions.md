# Prompt 26: Problems Encountered & Solutions

## Problem 1: Timezone Awareness in Named Window Ranges
- **Issue**: Authority operators in different geographical timezones (e.g. `Asia/Kolkata` vs `UTC`) require day boundaries aligned with local midnight rather than UTC midnight.
- **Solution**: Implemented Python standard `zoneinfo.ZoneInfo` in `normalize_time_range()` to convert local calendar days into UTC ISO timestamps before MongoDB querying.

## Problem 2: Alert Fatigue from Incident Surge Detection
- **Issue**: Sustained busy periods could repeatedly trigger duplicate incident surge notifications every few minutes.
- **Solution**: Implemented an in-memory / database-backed 30-minute cooldown window per jurisdiction per alert type with threshold checks.

## Problem 3: Collection Schema Flexibility in Testing
- **Issue**: Earlier test fixtures referenced `mock_db.responders` and `mock_db.incident_assignments`, whereas Prompt 26 services introduced `responder_profiles` and `responder_assignments`.
- **Solution**: Added attribute fallback resolvers `getattr(db, 'responder_profiles', getattr(db, 'responders', None))` across all analytical services, ensuring backward and forward test compatibility.
