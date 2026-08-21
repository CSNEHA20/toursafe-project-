# Architectural Decisions — Prompt 03: Real Geospatial Zone Foundation

## 1. RFC 7946 GeoJSON Standard Adherence
- **Decision**: Strictly enforce `[longitude, latitude]` coordinate ordering across all database storage, API schemas, and validation logic.
- **Rationale**: MongoDB's `2dsphere` spatial indexing and the GeoJSON specification (RFC 7946) require `[longitude, latitude]` order. Swapped coordinates cause catastrophic spatial query bugs and inversion of hemispheres.
- **Impact**: All endpoints and models enforce `[lon, lat]`. The map component handles conversion between Leaflet/React-Native `{ latitude, longitude }` objects and GeoJSON `[lon, lat]` tuples.

## 2. Public Map-Ready API vs Protected Authority API Separation
- **Decision**: Provide separate routers:
  - `/api/v1/zones` (Tourist / Public): Read-only, lightweight, filters to only active zones, serializes into map-ready format (`ZoneMapItem`).
  - `/api/v1/authority/zones` (Authority / Admin): Full CRUD, includes draft/inactive zones, supports status transitions, full property inspection, and audit history.
- **Rationale**: Minimizes payload size for mobile tourist clients, protects administrative operational controls, and isolates RBAC concerns cleanly.

## 3. Dedicated Immutable `ZoneAudit` Collection
- **Decision**: Store zone change history in a separate `zone_audits` collection indexed by `zone_id` and `changed_at`.
- **Rationale**: Ensures complete administrative accountability without inflating the `zones` document size over time. Captures `old_state`, `new_state`, `changed_by`, `action`, and timestamp for forensic audit trails.

## 4. Soft Delete as Default Operation
- **Decision**: Default `DELETE /api/v1/authority/zones/{id}` performs a soft deactivation (`is_active = false`, `status = "inactive"`). Hard deletion requires explicit query parameter `?hard_delete=true` and `admin` privileges.
- **Rationale**: Prevents accidental deletion of safety perimeters that may have historic incident records or ongoing references.

## 5. Development Geometry Tagging
- **Decision**: Label all initial seeded zones with `"dataset": "DEVELOPMENT GEOMETRY"`.
- **Rationale**: Directly satisfies prompt requirement to distinguish development and prototype boundaries from certified survey data while maintaining realistic geographic fidelity in Tamil Nadu tourist regions.
