# Realtime Results — TourSafe WebSocket Layer

## WebSocket Architecture
- **Client**: `frontend/lib/realtimeClient.ts`
- **Backend Router**: `backend/app/routers/realtime.py`
- **Endpoint**: `ws://localhost:8000/ws?token=<token>`
- **Dispatcher**: `frontend/lib/eventDispatcher.ts`

## Connection Lifecycle Verification
- **Eager Connection Audit**: Verified that importing `realtimeClient` does **NOT** eagerly attempt connection at import time.
- **Connection Trigger**: Connection is initiated explicitly when user session initializes or upon successful login (`realtimeClient.connect(token)`).
- **Graceful Disconnection**: Disconnecting clears timers, closes active socket channels, and updates UI status badges to `DISCONNECTED` or `OFFLINE` truthfully without displaying fake `LIVE` indicators.
- **Backoff & Reconnect**: Implements exponential backoff with jitter up to `maxReconnectDelay = 10000ms`.
