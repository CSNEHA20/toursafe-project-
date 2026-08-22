# Prompt 12: Problems Encountered and Solutions

## 1. Schema Enum Consistency Across Subsystems
- **Problem**: `IncidentStatus` and `IncidentSeverity` enums were defined in both `backend/app/schemas/safety.py` and `backend/app/schemas/emergency.py`. `IncidentSource` was defined in `emergency.py` but referenced in `safety.py`.
- **Solution**: Harmonized enums across both modules, ensuring `IncidentStatus` contains all states (`OPEN`, `ACKNOWLEDGED`, `ASSESSING`, `ASSIGNED`, `RESPONDING`, `MONITORING`, `ESCALATED`, `RESOLVED`, `CANCELLED`, `CLOSED`) and exported `IncidentSource` in both schemas.

## 2. Dynamic Database Resolution for Test Isolation
- **Problem**: When testing services with `monkeypatch.setattr(db_module, "get_database", ...)`, service modules that had imported `from ...core.database import get_database` held direct references to the original function binding rather than dynamically calling the patched module function.
- **Solution**: Refactored database imports in `incident_service.py`, `sos_service.py`, `responder_service.py`, `escalation_engine.py`, `notifications.py`, `repository.py`, and `emergency.py` to import `database as db_core` with dynamic helper `def get_database(): return db_core.get_database()`.

## 3. Router Collision Between Prompt 11 & Prompt 12 Endpoints
- **Problem**: `safety_router` in `safety.py` and `emergency_router` in `emergency.py` both defined authority incident endpoints (`/acknowledge`, `/resolve`, `/metrics`). Because `safety_router` was mounted first in `main.py`, FastAPI matched the Prompt 11 handlers which did not support Prompt 12 optimistic locking or resolution categories.
- **Solution**: Mounted `emergency_router` before `safety_router` in `main.py` and added all incident command handlers (`/acknowledge`, `/assess`, `/assign`, `/response-start`, `/escalate`, `/notes`, `/resolve`, `/cancel`, `/close`, `/metrics`, `/{incident_id}`) directly to `emergency_router`.

## 4. Test Mock MongoDB Collection Method Compatibility
- **Problem**: In `test_safety_e2e.py` and `test_safety_engine.py`, `MockMongoCollection` implemented `update_one` but lacked `replace_one`, causing `AttributeError` when `safety_repository.upsert_incident` executed.
- **Solution**: Added `replace_one` method to `MockMongoCollection` across test suites, and made `safety_repository.upsert_incident` fallback gracefully to `update_one` if `replace_one` is absent.
