# Architectural & Technical Decisions - Prompt 10

## 1. Ray-Casting Algorithm with Boundary Tolerance
- **Decision**: Implemented Jordan Curve Ray-Casting with an explicit vertex and edge geodesic epsilon buffer ($\epsilon = 0.5\text{ m}$) rather than bounding-box approximations or simplified polygon checks.
- **Rationale**: Strict adherence to RFC 7946 GeoJSON and accurate detection for complex non-convex wilderness boundaries (e.g. ravine edges and mountain ridgelines).

## 2. Temporal Confirmation & Fast-Path Hysteresis
- **Decision**: Required 3 consecutive confirmation samples when near boundaries ($d_{\text{boundary}} \le 15\text{ m}$), but allowed immediate 1-sample transitions when deep inside ($d > 15\text{ m}$).
- **Rationale**: Eliminates alert spam and state thrashing caused by GPS multipath reflections and boundary jitter without introducing noticeable latency when moving deep into a zone.

## 3. Non-Destructive Staleness Semantics
- **Decision**: Transitioned state to `STALE` without firing `zone.exited` when GPS updates cease ($> 60\text{ s}$).
- **Rationale**: A tourist who loses signal inside a dense forest or ravine is still physically inside that risk zone. Firing an exit event would falsely clear safety warnings on authority monitoring screens.

## 4. Multi-Zone Resolution via Maximum Risk Priority
- **Decision**: Allowed simultaneous active membership across overlapping polygons while deriving composite tourist status as `max(risk_level)` with priority `CRITICAL > HIGH > MEDIUM > LOW`.
- **Rationale**: Tourists frequently traverse nested or adjacent jurisdictions. The authority and tourist apps must always highlight the most severe immediate threat.

## 5. Storage Separation: Redis Active State vs. MongoDB Audit Trail
- **Decision**: Kept active snapshots in Redis (`toursafe:geofence:active:{tourist_id}`) with 300s TTL, and persisted confirmed transition records to MongoDB `zone_transitions`.
- **Rationale**: Delivers sub-millisecond query latency for high-frequency location updates while maintaining a durable, queryable history for authority audits and incident reviews.
