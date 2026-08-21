# TOURSAFE — PROMPT 10
## REAL-TIME GEO-FENCING ENGINE: GPS + GEOJSON ZONES, POINT-IN-POLYGON DETECTION, ZONE ENTRY / EXIT, BOUNDARY HANDLING, ZONE DWELLING, ZONE TRANSITIONS, ZONE RISK EVENTS, AUTHORITY REALTIME INTEGRATION

### Summary of Prompt Requirements:
1. Implement real-time geospatial geo-fencing engine matching real GPS telemetry against GeoJSON polygon boundaries.
2. Comply with RFC 7946 coordinates `[longitude, latitude]`.
3. Implement Jordan Curve point-in-polygon with polygon holes, MultiPolygons, geodesic distances, and perpendicular segment boundary distances.
4. Implement GPS accuracy buffering and boundary uncertainty classification.
5. Implement temporal hysteresis state machine to prevent boundary jitter.
6. Implement actual timestamp-based dwell tracking and threshold alerts.
7. Support concurrent multi-zone membership and highest-risk resolution.
8. Store ephemeral active states in Redis with TTL and persist transition history to MongoDB `zone_transitions`.
9. Dispatch real-time WebSocket events (`zone.entered`, `zone.exited`, `zone.dwell.threshold_reached`, `zone.membership.uncertain`, `zone.membership.stale`) to tourist and authority channels with deduplication.
10. Expose REST endpoints for tourist, authority, and dev diagnostics.
11. Integrate frontend UI in tourist/admin maps and dev diagnostics screen.
12. Create test suite with 100% pass rate and write comprehensive session documentation.
