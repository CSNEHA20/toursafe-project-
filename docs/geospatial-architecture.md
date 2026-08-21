# TourSafe Real Geospatial Architecture

## Overview

TourSafe provides an authoritative, real geospatial zone foundation for tourism safety and disaster response. It replaces static mock geofences with RFC 7946-compliant GeoJSON geometries stored in MongoDB with `2dsphere` spatial indexing, validated by strict coordinate bounds and ring closure rules, and audited for complete administrative traceability.

---

## 1. Coordinate Standard & RFC 7946 Compliance

All geospatial coordinates in TourSafe strictly follow the **RFC 7946 GeoJSON Standard**:
- **Coordinate Tuple Ordering**: `[longitude, latitude]` (where `-180.0 <= longitude <= 180.0` and `-90.0 <= latitude <= 90.0`).
- **Polygon LinearRings**:
  - Minimum of 4 coordinate pairs per linear ring.
  - Closed ring invariant: `ring[0] == ring[-1]` (first and last coordinate vertices must match).
  - Valid boundary bounds: coordinates must lie within real geographic limits.

### GeoJSON Geometry Models
- **`GeoJSONPoint`**: `{"type": "Point", "coordinates": [longitude, latitude]}`
- **`GeoJSONPolygon`**: `{"type": "Polygon", "coordinates": [[[lon1, lat1], [lon2, lat2], ..., [lon1, lat1]]]}`
- **`GeoJSONMultiPolygon`**: `{"type": "MultiPolygon", "coordinates": [[[[lon1, lat1], ..., [lon1, lat1]]]]}`

---

## 2. MongoDB Data Models & 2dsphere Indexes

### Collections

#### `zones`
```json
{
  "_id": "ObjectId(...)",
  "zone_id": "zone_kodaikanal_lake",
  "name": "Kodaikanal Lake Central Buffer Zone",
  "description": "Lake corridor safety perimeter with water emergency rescue station access.",
  "zone_type": "safe",
  "risk_level": "low",
  "status": "active",
  "is_active": true,
  "boundary": {
    "type": "Polygon",
    "coordinates": [
      [
        [77.4830, 10.2430],
        [77.4950, 10.2430],
        [77.4960, 10.2320],
        [77.4840, 10.2310],
        [77.4830, 10.2430]
      ]
    ]
  },
  "center": {
    "type": "Point",
    "coordinates": [77.4892, 10.2381]
  },
  "properties": {
    "dataset": "DEVELOPMENT GEOMETRY",
    "district": "Dindigul",
    "state": "Tamil Nadu"
  },
  "created_at": "2026-08-21T00:00:00Z",
  "updated_at": "2026-08-21T00:00:00Z",
  "created_by": "system",
  "updated_by": "system"
}
```

#### `zone_audits`
```json
{
  "_id": "ObjectId(...)",
  "audit_id": "audit_uuid_1234",
  "zone_id": "zone_kodaikanal_lake",
  "action": "create",
  "changed_by": "admin_user_id",
  "changed_at": "2026-08-21T00:00:00Z",
  "old_state": null,
  "new_state": { ... },
  "change_summary": "Created zone with type=safe, risk_level=low"
}
```

### MongoDB Spatial Indexes
1. `zones.boundary` -> `2dsphere` index for spatial queries (`$geoIntersects`, `$geoWithin`).
2. `zones.center` -> `2dsphere` index for proximity queries (`$near`, `$nearSphere`, `$geoNear`).
3. `zones.name` + `zones.description` -> Text index for fast keyword search.
4. `zones.status` + `zones.is_active` -> Compound index for fast active zone filtering.
5. `zone_audits.zone_id` + `zone_audits.changed_at` -> Compound index for audit trail history.

---

## 3. API Contract & Serialization

### Tourist / Map-Ready API (Public / Read-Only)
- **`GET /api/v1/zones`**:
  - Query parameters: `zone_type`, `risk_level`, `skip`, `limit`.
  - Filter: Returns only `is_active == True` and `status == "active"` zones.
  - Serialization: Map-ready lightweight representation `ZoneMapItem` (`zone_id`, `name`, `description`, `type`, `risk_level`, `status`, `geometry`, `center`, `properties`).
- **`GET /api/v1/zones/{zone_id}`**:
  - Returns specific active zone by ID.

### Authority / Admin Zone Management API (Protected, `authority`/`admin` Role)
- **`POST /api/v1/authority/zones`**:
  - Validates RFC 7946 GeoJSON boundary and computes center if omitted.
  - Inserts new Zone into MongoDB.
  - Writes immutable audit log into `zone_audits`.
- **`GET /api/v1/authority/zones`**:
  - Query parameters: `q` (text search), `status`, `zone_type`, `risk_level`, `skip`, `limit`, `sort_by`, `sort_order`.
  - Returns paginated list of all zones (including drafts and inactive).
- **`GET /api/v1/authority/zones/{zone_id}`**:
  - Returns full administrative zone record.
- **`PATCH /api/v1/authority/zones/{zone_id}`**:
  - Validates updated fields and boundary geometry.
  - Enforces status transition rules (`draft` -> `active` / `inactive`, `active` -> `inactive`, `inactive` -> `active`).
  - Writes audit trail with `old_state`, `new_state`, and `change_summary`.
- **`DELETE /api/v1/authority/zones/{zone_id}`**:
  - Soft delete (default): sets `status = "inactive"`, `is_active = false`, logs `deactivate` audit.
  - Hard delete (`?hard_delete=true`, admin only): removes document from `zones`, logs `delete` audit.
- **`GET /api/v1/authority/zones/{zone_id}/audits`**:
  - Returns chronological immutable audit entries for the zone.

---

## 4. Frontend Map Layer & UI Architecture

- **`RealMap.web.tsx` & `RealMap.native.tsx`**:
  - Supports rendering multiple GeoJSON polygons simultaneously via `polygons` prop.
  - Color-coded risk styling:
    - `low` / `safe` -> Emerald (`#10b981`)
    - `medium` / `warning` -> Amber (`#f59e0b`)
    - `high` / `critical` / `restricted` -> Rose/Red (`#ef4444`)
  - Interactive popups displaying zone names and risk levels.
- **Tourist Map (`app/tourist/(tabs)/map.tsx`)**:
  - Connects to `zoneApi.getAll()` for live active safety boundaries.
  - Handles Loading, Error, Empty, and Success states with retry capability.
  - Displays safety anchors and corridor alerts for Nilgiris and Kodaikanal.
- **Admin Map (`app/admin/(tabs)/map.tsx`)**:
  - Real-time command overview of all active safety zones and spatial boundaries.
- **Admin Zones Management (`app/admin/(tabs)/zones.tsx`)**:
  - Search, filter by type/status/risk, create new zone with GeoJSON inputs and development presets, edit existing zones, transition status, deactivate/delete, and inspect immutable audit trails.

---

## 5. Development Seeding & Geometry Tagging

All initial development zones are tagged with `"dataset": "DEVELOPMENT GEOMETRY"` in `properties` to clearly distinguish development/staging geometries from production-verified cartographic surveys.
Initial seeded zones cover key Tamil Nadu / Nilgiris tourism corridors:
1. `zone_kodaikanal_lake`: Kodaikanal Lake Central Buffer Zone (`safe`, `low`)
2. `zone_guna_caves`: Guna Caves Hazard Corridor (`restricted`, `critical`)
3. `zone_coakers_walk`: Coaker's Walk Pedestrian Waypoint (`safe`, `low`)
4. `zone_berijam_lake`: Berijam Lake Reserve Forest Corridor (`warning`, `medium`)
5. `zone_pillar_rocks`: Pillar Rocks Cliff Observation Zone (`warning`, `medium`)
6. `zone_ooty_botanical`: Ooty Government Botanical Garden Zone (`safe`, `low`)
7. `zone_ooty_lake`: Ooty Lake Waterfront Buffer Zone (`safe`, `low`)
8. `zone_doddabetta`: Doddabetta Peak Summit Corridor (`warning`, `medium`)
