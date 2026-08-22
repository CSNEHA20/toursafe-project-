# Prompt 14 Problems & Solutions

## Problem 1: Relative Import Beyond Top-Level Package
- **Cause**: In `notification_center.py` and `providers/*.py`, relative import dots exceeded package depth when imported from root.
- **Solution**: Adjusted relative dot counts to match exact module directory levels (3 dots for `app/services/notifications/notification_center.py` to reach `app.core`, 4 dots for sub-packages).
- **Verification**: `pytest tests/test_notifications.py` loaded modules cleanly and verified all imports.

---

## Problem 2: JWT Access Token Keyword Argument Mismatch in Tests
- **Cause**: Test fixtures called `create_access_token(data={"user_id": ..., "role": ...})`, whereas `create_access_token` expected positional parameters `(user_id: str, role: str)`.
- **Solution**: Updated test fixtures to pass `("auth_user_001", "authority")` positionally.
- **Verification**: `test_notifications_api_endpoints` executed and passed all 6 endpoint assertions.

---

## Problem 3: TypeScript Event Listener Method Name in RealtimeClient
- **Cause**: `RealtimeClient` defined `onEvent(...)` for subscribing to typed WebSocket events, whereas frontend components initially invoked `.on(...)`.
- **Solution**: Updated `NotificationBellButton.tsx` and `NotificationCenterModal.tsx` to invoke `realtimeClient.onEvent("notification.created", ...)`.
- **Verification**: `npx tsc --noEmit` exited with code 0 (0 errors).
