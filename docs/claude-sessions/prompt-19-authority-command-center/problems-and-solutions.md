# TourSafe Prompt 19 Problems & Solutions Record

## Problem 1: Pytest Python Import Path Resolution
- **Cause**: Running `python -m pytest` from repository root failed to resolve `from app...` imports without `PYTHONPATH` set to `backend`.
- **Solution**: Executed pytest with `$env:PYTHONPATH="backend"` in PowerShell.
- **Verification**: All backend unit and integration tests executed and passed cleanly.

## Problem 2: Missing TypeScript Union Member for WebSocket Connecting State
- **Cause**: `RealtimeConnectionState` in `@/types/realtime` includes `"connecting"`, but `commandCenterStore` initially typed `connectionState` without `"connecting"`.
- **Solution**: Expanded the union in `commandCenterStore.ts` to `"connecting" | "connected" | "reconnecting" | "disconnected" | "error"`.
- **Verification**: Typecheck passed with 0 errors across all Command Center modules.

## Problem 3: Preventing Event Duplication on Realtime Ingestion
- **Cause**: High-frequency WebSocket reconnects or duplicate network packets could trigger duplicate state transitions or duplicate feed items.
- **Solution**: Implemented an in-memory sliding window cache of `processedEventIds` (capped at 1000 items) and version/timestamp monotonicity checks.
- **Verification**: Verified in store unit tests and realtime handler flow.
