# TourSafe Prompt 33 — Problems and Solutions

## Problem 1: Windows Console Unicode Encoding during CLI Execution
- **Symptom**: `scripts/synthetic_smoke_test.py` threw `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f680'` under Windows default console cp1252 codepage.
- **Root Cause**: Emoji characters in terminal print statements fail on non-UTF8 standard Windows shells.
- **Solution**: Replaced emoji characters in all automation scripts with standard ASCII prefixes (`[OK]`, `[STEP]`, `[SUCCESS]`, `[FAIL]`), ensuring clean execution across all Linux, macOS, and Windows runtime shells.

## Problem 2: Signal Schema Attribute Alignment in Synthetic Smoke Runner
- **Symptom**: Initial smoke test instantiation of `SafetySignal` failed on enum values (`SignalType.ZONE_BREACH` instead of `SignalType.ZONE_ENTERED`, missing `source` and `value` fields).
- **Root Cause**: Field names in script diverged slightly from canonical Pydantic model in `backend/app/schemas/safety.py`.
- **Solution**: Aligned `SafetySignal` arguments with schema (`source="synthetic_smoke_test"`, `value={...}`, `quality=SignalQuality.GOOD`, `metadata={"confidence": 0.95}`).

## Problem 3: Development Zone Seeding in Production Environments
- **Symptom**: `backend/app/main.py` previously attempted to seed development geospatial zones automatically on every application boot.
- **Root Cause**: Development convenience logic executed indiscriminately regardless of `ENVIRONMENT` setting.
- **Solution**: Guarded `seed_initial_zones(db)` with `if settings.environment.lower() not in ("production", "prod"):` so that production launches begin with clean, compliant state stores.
