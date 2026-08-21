# Problems and Solutions - Prompt 10: Real-Time Geo-Fencing Engine

## Problem 1: Route Collision on Static vs Parameterized Authority Endpoints
- **Symptom**: `GET /api/v1/authority/zones/live-occupancy` returned 404 or validation errors because `authority_zones_router` had `GET /{zone_id}` registered with identical prefix.
- **Root Cause**: FastAPI matched `"live-occupancy"` as the path parameter `{zone_id}` of the zone CRUD router.
- **Solution**: Included `geofence_router` before `authority_zones_router` in `app.include_router()` in `backend/app/main.py`.

## Problem 2: Dynamic Database Access in Test Fixtures
- **Symptom**: Pytest location test suite encountered `AttributeError` on `MockAppDatabase` when accessing `zones` and `zone_transitions`.
- **Root Cause**: `MockAppDatabase` lacked initialized attributes for the new collections, and module-level imports of `get_database` captured static references.
- **Solution**: Added `__getattr__` and explicit collection instances to `MockAppDatabase`, and updated `repository.py` to use `from ...core import database as db_core` calling `db_core.get_database()`.

## Problem 3: WebSocket Subscription Method Name in Frontend
- **Symptom**: Frontend TypeScript compilation failed with `Property 'on' does not exist on type 'RealtimeClient'`.
- **Root Cause**: The client method was defined as `onEvent(eventType, handler)`.
- **Solution**: Updated `frontend/app/dev/geofence.tsx` to use `realtimeClient.onEvent`.
