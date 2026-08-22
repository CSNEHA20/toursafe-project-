# Problems and Solutions — Prompt 11: Safety Orchestration Engine

## 1. Problem: Python Enum Identity Across Relative vs Absolute Import Namespaces
- **Symptom**: In test runs, `IncidentStatus.RESOLVED` comparisons in `can_transition` failed even when both were `RESOLVED`, because `app.schemas.safety` and `backend.app.schemas.safety` produced different enum instances in Python's `sys.modules`.
- **Solution**: Updated `SafetyStateMachine.is_valid_transition` and `IncidentLifecycleManager.can_transition` to extract string values via `.value` or `str()` and compare value sets. This guarantees robust compatibility across all test environments and module loading strategies.

## 2. Problem: Offline MongoDB Connection Timeouts in Local Test Environments
- **Symptom**: Integration tests connecting to `safety_repository` waited on 20-30s MongoDB TCP connect timeouts when running on systems without a running local mongod daemon.
- **Solution**: Built an in-memory `MockAppDatabase` with `MockMongoCollection` fixture in tests, monkeypatching `get_database` across routers and repositories. Unit and end-to-end tests now execute in under 8 seconds with zero external network or database dependencies.

## 3. Problem: Tourist Safety Status Lookups by User ID vs Tourist ID
- **Symptom**: Tourist JWT tokens encode `user_id`, while sensor streams and tracking sessions may be keyed by `tourist_id` from the profile document.
- **Solution**: Enhanced `get_tourist_safety_me` in `backend/app/routers/safety.py` to first check Redis for `user_id`, and if not found, perform a fast fallback lookup against `db.tourists` for the matching profile `tourist_id`.

## 4. Problem: Recovery Cooldown Bypassed on Clean Normal Windows
- **Symptom**: When signals were normal, `rule_engine.evaluate_signals` was checking only `previous_state in (INCIDENT, INCIDENT_CANDIDATE, ELEVATED)` and falling through to `NORMAL` if `previous_state == RECOVERING`.
- **Solution**: Added `SafetyState.RECOVERING` to the recovery gate check in `rules.py` line 253, ensuring that every evaluation cycle during recovery actively checks the 20s cooldown timer and retains `RECOVERING` until the timer completes.
