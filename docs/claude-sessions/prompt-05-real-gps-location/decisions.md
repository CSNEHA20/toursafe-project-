# Prompt 5: Architecture Decisions

## Decision 1: Dedicated Location Service vs Inline Component Subscriptions
- **Decision**: Centralize all GPS subscription management and coordinate processing inside `LocationTrackingService` and `useLocationStore`.
- **Reason**: React components mount and unmount during tab navigation. If a component manages the subscription, navigating away kills tracking.
- **Alternatives**: Managing subscriptions in `useEffect` in `app/tourist/(tabs)/map.tsx`.
- **Why Selected**: Ensures uninterrupted foreground and background tracking across screen transitions.

## Decision 2: Redis Live State with 120s TTL vs Direct MongoDB Read
- **Decision**: Store the latest live location per tourist in Redis (`live_location:tourist:{tourist_id}`) with a 120s TTL, with MongoDB serving permanent history.
- **Reason**: 1 Hz GPS updates from thousands of tourists would create high write and read load if queried on every live map poll. Redis provides sub-millisecond lookups and automatic expiration for stale tourists.
- **Alternatives**: Polling MongoDB `location_history` collection directly.
- **Why Selected**: Decouples fast ephemeral live tracking state from persistent historical storage.

## Decision 3: Zero-Trust Tourist Identity on Location Ingest
- **Decision**: The backend derives the `tourist_id` strictly from the JWT authentication context and rejects/ignores client-provided identity fields.
- **Reason**: Prevents malicious actors from spoofing GPS coordinates for other tourists.
- **Alternatives**: Trusting `tourist_id` from the request JSON body.
- **Why Selected**: Critical for tourist safety and tamper-proof location attribution.

## Decision 4: Separation of GPS Updates from Future 50 Hz IMU Telemetry
- **Decision**: Process 1 Hz GPS location fixes via HTTP REST `/api/v1/location/update` with real-time WebSocket broadcast (`location.updated`), keeping it separate from future 50 Hz IMU sensor streaming.
- **Reason**: 1 Hz GPS coordinates require MongoDB persistence and GeoJSON 2dsphere indexing per fix. 50 Hz IMU streams require windowed batching and binary/WebSocket frame streaming. Mixing them prematurely would degrade performance.
- **Alternatives**: Forcing 1 Hz GPS into a raw binary telemetry socket stream immediately.
- **Why Selected**: Clean separation of concerns matching the TourSafe system specifications.
