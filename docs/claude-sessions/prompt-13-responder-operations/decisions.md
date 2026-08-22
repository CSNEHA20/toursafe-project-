# Design Decisions — Prompt 13

1. **No Autonomous Dispatch**:
   - Dispatching field responders to incidents must always involve explicit Authority Command action or transparent recommendation scoring. The recommendation service provides pure deterministic scoring based on real geodesic distance and capability matching.

2. **Haversine Geodesic Distance vs External Routing API**:
   - Built an in-house exact Haversine mathematical calculation for distance ranking. Avoided relying on external rate-limited or simulated routing APIs for deterministic behavior.

3. **Dual-Tier GPS Location Strategy**:
   - High frequency updates are written to Redis with 120s TTL for millisecond dispatch lookup, while also being appended to MongoDB `responder_location_history` for full incident reconstruction.

4. **Proximity Verification with Auditable Fallback**:
   - Responders marking arrival on scene are validated against incident coordinates within 500 meters. If GPS jitter or deep canyon interference prevents verification, `force_override=True` is allowed with mandatory audit logging.

5. **Anti-Concurrency Atomic Locks**:
   - `find_one_and_update` on MongoDB ensures only one incident can claim a responder at a time, eliminating double-dispatch race conditions.
