# TourSafe Prompt 19 Architectural Decisions

## Decision 1: Authoritative Backend Snapshot + Realtime Stream Model
- **Reason**: Prevents event replay gaps and empty UI states on initial page load or following WebSocket disconnects.
- **Alternatives**: Client-side reconstruction purely from event streams or periodic polling.
- **Why Selected**: Snapshots provide immediate complete state on login or reconnect, while WebSocket handles low-latency incremental state transitions.

## Decision 2: Centralized Command Center Zustand Store (`useCommandCenterStore`)
- **Reason**: Avoids redundant WebSocket subscriptions across disparate child components and maintains unified state across map, queue, command panel, and event stream.
- **Alternatives**: Separate localized stores for incidents, responders, and map pins.
- **Why Selected**: Operational decision support requires correlated context (e.g. clicking an incident automatically highlights its assigned responder, updates map focus, and filters the event stream).

## Decision 3: Location Staleness Degradation Engine (LIVE -> RECENT -> STALE -> UNKNOWN)
- **Reason**: Essential for government safety operations so operators never mistake lack of telemetry data for "tourist is safe".
- **Alternatives**: Showing all last-known locations as live until manually dismissed.
- **Why Selected**: Enforces strict operational honesty by visibly marking markers as stale or unknown after configurable thresholds without moving the marker.

## Decision 4: Optimistic Mutations with Rollback
- **Reason**: Provides immediate responsive feedback for operators during critical response workflows while ensuring backend state remains the final authority.
- **Alternatives**: Blocking UI until server response or fire-and-forget UI updates.
- **Why Selected**: Immediate UI responsiveness combined with reliable rollback on 409 conflict or network error guarantees both speed and consistency.
