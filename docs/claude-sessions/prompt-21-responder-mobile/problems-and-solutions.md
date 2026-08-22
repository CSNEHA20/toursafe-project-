# Problems and Solutions — Prompt 21: Responder Mobile Application

## 1. Pytest MockDatabase Missing Method & Dot-Notation Filtering
- **Problem**: In `backend/tests/test_responder_field_operations.py`, `MockCollection` lacked `find_one_and_update`, and did not support nested dot-notation queries (e.g. `"notes_list.client_note_id"`).
- **Solution**: Added `find_one_and_update` to `MockCollection` and updated `sync_field_notes` in `assignment_service.py` to inspect the incident's `notes_list` array directly in memory, making it robust across both MongoDB and test mocks.

## 2. Status Type Comparison (Enum vs String) in Handover Request
- **Problem**: When comparing `assignment.status` in `request_handover()`, if `assignment.status` was serialized as a string vs enum, comparison could fail.
- **Solution**: Normalised `status_val = assignment.status.value if hasattr(assignment.status, "value") else str(assignment.status)` and verified inclusion against `("ACCEPTED", "ACTIVE", "PENDING")`.

## 3. AssignmentRecord Schema Missing Cancellation Audit Fields
- **Problem**: Calling `request_handover` attempted to populate `cancelled_at` and `cancellation_reason` on `AssignmentRecord`, causing a Pydantic validation error.
- **Solution**: Added `cancelled_at: Optional[str] = None` and `cancellation_reason: Optional[str] = None` to `AssignmentRecord` in `backend/app/schemas/emergency.py`.

## 4. TypeScript Unit Name vs Callsign Interface Conflict
- **Problem**: In `frontend/app/responder/diagnostics.tsx`, `profile.active_unit.name` caused a TypeScript compilation error because `ResponderUnitRecord` defines `callsign`.
- **Solution**: Updated `diagnostics.tsx` to reference `profile.active_unit.callsign`.
