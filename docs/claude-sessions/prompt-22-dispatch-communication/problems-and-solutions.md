# Problems and Solutions: Prompt 22 — Dispatch, Communication & Multi-Party Incident Coordination

## 1. Mock Database Nested Field Filtering

- **Problem**: When evaluating MongoDB queries with nested dot notation (such as `"acknowledged_by.actor_id": {"$ne": user_id}` and `"deleted_at": None`), in-memory test mocks returned inaccurate document counts or failed to match records where fields were `None`.
- **Root Cause**: The mock implementation did not handle list recursion when navigating nested dot-separated keys, and dropped `None` values prematurely during path traversal.
- **Solution**: Enhanced `MockCollection._matches` to recursively expand array elements on dot-separated keys and treat empty resolved value paths as `[None]`, ensuring full compatibility with MongoDB query semantics.

---

## 2. Missing Schema Import in Handover Workflow

- **Problem**: In `assignment_service.request_handover`, a warning `name 'ChannelParticipantUpdateRequest' is not defined` was caught during channel status transition.
- **Root Cause**: `ChannelParticipantUpdateRequest` was referenced in the handover logic but omitted from the top-level import statement in `assignment_service.py`.
- **Solution**: Imported `ChannelParticipantUpdateRequest` from `app.schemas.emergency` in `assignment_service.py`.

---

## 3. Backwards Compatibility with Legacy `OperationalMessageCreateRequest`

- **Problem**: Earlier test suites (`test_responder_operations.py`) invoked `messaging_service.send_message(incident_id=..., sender_type="RESPONDER", req=OperationalMessageCreateRequest(...))`, which conflicted with the new strongly-typed `MessageSendRequest` and `sender_role` signature.
- **Root Cause**: Parameter signature evolved during multi-party channel refactoring.
- **Solution**: Added polymorphic parameter resolution in `send_message` to accept both `sender_role` and `sender_type`, and dynamically cast legacy `OperationalMessageCreateRequest` objects into `MessageSendRequest` records.

---

## 4. Test Suite Channel System Message Count Assertion

- **Problem**: `test_incident_assignment_lifecycle_and_proximity_arrival` failed on `assert len(messages) == 1` after creating and accepting an assignment.
- **Root Cause**: The updated `assignment_service.py` automatically emits rich system messages into the incident channel upon assignment and acceptance, meaning multiple messages exist in the channel history.
- **Solution**: Updated the test assertion to check for message presence (`assert any(m.message_id == msg.message_id for m in messages)`), accurately validating multi-party system history.
