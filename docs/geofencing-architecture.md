# TourSafe Real-Time Geo-Fencing Architecture & Specification

## 1. Executive Summary & Problem Domain
The TourSafe Real-Time Geo-Fencing Engine provides high-precision, low-latency spatial boundary monitoring for tourist safety across wilderness trails, hazardous terrain, high-altitude regions, and urban tourism corridors (e.g., Kodaikanal Lake, Nilgiris Reserve, Pillar Rocks). The engine ingests continuous 1 Hz GPS telemetry from tourist devices, correlates locations against authoritative GeoJSON polygon geometries, mitigates physical sensor jitter through temporal hysteresis, tracks dwell durations, resolves overlapping multi-zone risks, maintains active states in Redis, and persists auditable transition histories in MongoDB.

---

## 2. Spatial Coordinate System & RFC 7946 Standard
TourSafe strictly adheres to the **RFC 7946 GeoJSON Standard** and **WGS-84 (EPSG:4326)** reference ellipsoid:
- Coordinate tuples are strictly ordered as `[longitude, latitude]` with elevation as an optional third scalar `[lon, lat, alt]`.
- Longitude range: `[-180.0, +180.0]` degrees.
- Latitude range: `[-90.0, +90.0]` degrees.
- Polygon rings follow the right-hand rule: exterior boundary counter-clockwise, interior holes clockwise.

```
Coordinate Array: [77.4892, 10.2381]  --> [Longitude, Latitude]
```

---

## 3. Point-in-Polygon Engine (Jordan Curve Theorem & Ray Casting)
Point-in-polygon (PIP) determination is computed using the **Jordan Curve Ray-Casting Algorithm** augmented with exact boundary edge and vertex tolerance:
1. **Bounding Box Pre-Filtering**: Fast in-memory AABB (Axis-Aligned Bounding Box) evaluation rejects non-candidate geometries in $O(1)$ time.
2. **Ray-Casting Algorithm**: A horizontal ray is cast from $(x_p, y_p)$ to $+X_\infty$. The count of intersections with polygon segment $(x_i, y_i) \to (x_{i+1}, y_{i+1})$ determines containment:
   $$\text{intersect} \iff (y_i > y_p) \neq (y_{i+1} > y_p) \land \left( x_p < \frac{(x_{i+1} - x_i)(y_p - y_i)}{y_{i+1} - y_i} + x_i \right)$$
3. **Boundary Edge/Vertex Tolerance**: Points within geodesic $\epsilon = 0.5\text{ m}$ of any vertex or segment are classified as `ContainmentStatus.ON_BOUNDARY`.

---

## 4. Polygon Holes & MultiPolygon Handling
- **Interior Rings (Holes)**: A point is strictly inside a `Polygon` if and only if it is inside the exterior ring `coordinates[0]` AND outside all interior exclusion rings `coordinates[1..N]`.
- **MultiPolygon**: A point is inside a `MultiPolygon` if it is contained within any of the disjoint component polygons.

---

## 5. Geodesic Distance Calculations (WGS-84 Haversine & Cross-Track)
Distance between two geographic coordinates $(lat_1, lon_1)$ and $(lat_2, lon_2)$ on a spherical Earth of radius $R = 6,371,000\text{ m}$ is computed via the Haversine formula:
$$a = \sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)$$
$$c = 2 \cdot \arctan2\left(\sqrt{a}, \sqrt{1 - a}\right)$$
$$d = R \cdot c$$

Point-to-segment perpendicular distance computes the projection fraction $t = \frac{\vec{AP} \cdot \vec{AB}}{\|\vec{AB}\|^2}$ clamped to $[0, 1]$, interpolating the nearest segment point $P_{\text{proj}}$ on the ellipsoid.

---

## 6. Minimum Boundary Distance Computation
The minimum distance from point $P$ to a zone geometry $\mathcal{G}$ computes the minimum geodesic distance across all linear segments comprising both outer rings and interior hole rings:
$$d_{\text{boundary}}(P, \mathcal{G}) = \min_{s \in \text{Edges}(\mathcal{G})} \text{distance\_to\_segment}(P, s)$$

This scalar distance $d_{\text{boundary}}$ drives boundary proximity alerts, confidence decay, and hysteresis thresholds.

---

## 7. GPS Accuracy, Dilution of Precision & Uncertainty Models
Raw GPS fixes exhibit radial positional error modeled as circular uncertainty $\sigma_{\text{accuracy}}$:
- `EXCELLENT`: $\sigma \le 5\text{ m}$
- `GOOD`: $5\text{ m} < \sigma \le 15\text{ m}$
- `MODERATE`: $15\text{ m} < \sigma \le 30\text{ m}$
- `POOR`: $30\text{ m} < \sigma \le 50\text{ m}$
- `UNRELIABLE`: $\sigma > 50\text{ m}$

---

## 8. Boundary Uncertainty Buffer & Overlap Calculus
When the tourist's GPS accuracy circle radius $r = \sigma_{\text{accuracy}}$ overlaps the polygon boundary:
$$d_{\text{boundary}} < \sigma_{\text{accuracy}}$$
The position is marked as **uncertain** because the true ground coordinate could lie either inside or outside the zone.

---

## 9. Confidence Scoring Formulation
Membership confidence $C \in [0.0, 1.0]$ scales based on boundary distance and GPS accuracy:
- If strictly inside:
  $$C_{\text{inside}} = \min\left(1.0, 0.5 + \frac{d_{\text{boundary}}}{2 \cdot \max(\sigma_{\text{accuracy}}, 1.0)}\right)$$
- If strictly outside:
  $$C_{\text{outside}} = \min\left(1.0, 0.5 + \frac{d_{\text{boundary}}}{2 \cdot \max(\sigma_{\text{accuracy}}, 1.0)}\right)$$
- If GPS is `UNRELIABLE` ($\sigma > 50\text{ m}$): $C = \max(0.1, C \cdot 0.5)$.

---

## 10. Temporal Hysteresis State Machine & Jitter Damping
To prevent rapid flickering (`entered` $\leftrightarrow$ `exited`) caused by GPS jitter near boundaries, the engine executes a discrete hysteresis state machine:

```
           +----------------------------------------------------+
           |                                                    |
           v                                                    |
     [ OUTSIDE ]                                                |
          |  (1 sample if deep inside / d > 15m)                |
          |  OR (3 consecutive samples if near boundary)        |
          v                                                     |
  [ ENTER_CANDIDATE ] ---> [ INSIDE ]                           |
                             |   |                              |
      (GPS stale > 60s)      |   |  (1 sample if d > 15m)       |
      (No exit emitted!)     |   |  OR (3 consecutive samples)  |
                             v   v                              |
                         [ STALE ]  [ EXIT_CANDIDATE ] --------+
```

### State Confirmation Parameters:
- `CONFIRM_SAMPLE_COUNT = 3`: 3 consecutive samples required when within $15\text{ m}$ boundary buffer.
- `FAST_PATH_DISTANCE_METERS = 15.0`: Instant transition (1 sample) when tourist is $> 15\text{ m}$ deep inside or outside.

---

## 11. Dwell Tracking & Threshold Crossing Mechanics
- When `zone.entered` is confirmed, `entered_at` is initialized to the current GPS timestamp.
- For each subsequent sample inside the zone:
  $$\text{dwell\_duration\_seconds} = \text{timestamp} - \text{entered\_at}$$
- Configurable zone dwell threshold (default: $1800\text{ s}$ / $30\text{ min}$):
  - When dwell exceeds threshold and `dwell_threshold_notified == False`, a `zone.dwell.threshold_reached` event is fired.
  - Event is marked `dwell_threshold_notified = True` to prevent repeated alert spam.

---

## 12. Multi-Zone Concurrent Membership & Highest-Risk Resolution
Tourists may legitimately reside inside multiple overlapping zones (e.g., inside both a broad "Nilgiris Biosphere Safe Zone" and a nested "Pillar Rocks High Cliff Danger Zone"):
- Each zone maintains independent state machine tracking.
- The composite tourist state computes:
  - `highest_risk_level = max(zone.risk_level for zone in active_zones)` using priority: `CRITICAL > HIGH > MEDIUM > LOW`.
  - `primary_zone_type = max_risk_zone.zone_type`.

---

## 13. MongoDB 2dsphere Spatial Candidate Indexing & Query Pipeline
To scale across thousands of zones without running $O(N)$ geometry evaluations:
1. `zones` collection contains a 2dsphere index on `boundary` and `center`.
2. Spatial candidate query executes `$geoIntersects` with Point geometry + `$nearSphere` on center within buffer.
3. Fallback evaluates in-memory bounding-box intersection.
4. Transition history is persisted to `zone_transitions` with compound indexes on `(tourist_id, timestamp)`, `(zone_id, timestamp)`, and `(location)` 2dsphere.

---

## 14. Redis Ephemeral Active State Management & TTL Architecture
- Key: `toursafe:geofence:active:{tourist_id}`
- Value: Serialized JSON of `TouristGeofenceSnapshot`.
- TTL: $300\text{ s}$ ($5\text{ min}$) automatic refresh on each GPS update.
- Graceful degradation: in-memory store activated if Redis is unreachable.

---

## 15. Non-Destructive GPS Staleness & Disconnection Handling
When a tourist enters a tunnel, canyon, or loses GPS signal ($> 60\text{ s}$):
- The engine transitions state to `ZoneMembershipState.STALE`.
- **CRITICAL**: The engine does NOT fire `zone.exited`.
- Emits `zone.membership.stale` so authority maps highlight the last known location with a stale warning indicator.

---

## 16. Real-Time Event Architecture & Multi-Channel Distribution
Confirmed state transitions build a `RealtimeEventEnvelope` dispatched via WebSocket ConnectionManager:
- Destination channel 1: `tourist:{tourist_id}` (personal safety alerts, guidance).
- Destination channel 2: `authority:operations` (command center live dashboard, situational awareness).

Supported event types:
- `zone.entered`
- `zone.exited`
- `zone.dwell.threshold_reached`
- `zone.membership.uncertain`
- `zone.membership.stale`

---

## 17. Event Deduplication Engine & Suppression Windows
- Deduplication cache key: `{tourist_id}:{zone_id}:{event_type}`
- Sliding suppression window: $10.0\text{ s}$ for rapid duplicate transitions; $30.0\text{ s}$ for uncertainty warnings.

---

## 18. Authority Command Map & Operations Integration
The Authority Command Map (`frontend/app/admin/(tabs)/map.tsx`) renders:
- Real GeoJSON polygon geometries color-coded by risk level (Green: Low/Safe, Amber: Medium/Warning, Orange: High, Red: Critical).
- Real-time tourist markers with active zone badges and dwell counters.
- Live occupancy counts per zone.

---

## 19. REST API Specification
- `GET /api/v1/tourists/me/zones/current`: Current active zones, highest risk, dwell times.
- `GET /api/v1/tourists/me/zones/history`: Paginated transition history for authenticated tourist.
- `GET /api/v1/authority/tourists/{tourist_id}/zones/current`: Authority inspection of tourist geofence state.
- `GET /api/v1/authority/tourists/{tourist_id}/zones/history`: Authority audit of tourist transitions.
- `GET /api/v1/authority/zones/live-occupancy`: Active tourist counts across all zones.
- `GET /api/v1/dev/geofence/diagnostics/{tourist_id}`: Development telemetry and containment diagnostics.

---

## 20. Security, Privacy, and Authorization Boundaries
- Strict RBAC: Tourist can only query their own geofence snapshot (`me`). Role `authority` or `admin` required for authority endpoints.
- Tourist identities are cryptographically resolved from verified JWT claims.
- Location telemetry is bounded within authorized session windows.
