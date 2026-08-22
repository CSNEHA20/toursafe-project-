# Problems and Solutions — Prompt 31

## Problem 1: In-Memory Enum vs String Serialization in Async Services
- **Problem:** When Pydantic models with `use_enum_values=True` were serialized, certain nested fields like `scope` or `cat` passed as string literals caused `AttributeError: 'str' object has no attribute 'value'`.
- **Solution:** Updated service helper functions to check `hasattr(obj, "value")` and fall back to `str(obj)` gracefully, ensuring full compatibility across models, API payloads, and test fixtures.

## Problem 2: DeletionBehavior vs ArchiveBehavior Schema Alignment
- **Problem:** Initial baseline retention policy seed entries for `INCIDENT` and `AUDIT` used `DeletionBehavior.ARCHIVE_ENCRYPTED`, which belongs to `ArchiveBehavior`.
- **Solution:** Aligned the field to valid `DeletionBehavior` enums (`PSEUDONYMIZE_ANONYMIZE`, `HARD_DELETE`, `SOFT_DELETE`), resolving Pydantic validation errors.

## Problem 3: Safe Retention Sweep Cutoff Logic
- **Problem:** In retention unit tests, when database was empty, `resolve_policy` fell back to a default 90-day window, preventing 60-day test telemetry from being purged.
- **Solution:** Implemented a category-specific fallback map in `resolve_policy` (30 days for `TELEMETRY`, 60 days for `AI`, 90 days for `LOCATION`, 365 days for `KYC`, 730 days for `INCIDENT`, 1825 days for `AUDIT`), ensuring accurate default behavior even before seeding.
