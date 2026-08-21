# Problems & Solutions — Prompt 03: Real Geospatial Zone Foundation

## 1. GeoJSON Ring Closure & Coordinate Bound Validation
- **Problem**: Malformed coordinates or unclosed LinearRings (where first coordinate != last coordinate) cause MongoDB `2dsphere` index creation or `$geoIntersects` queries to fail with unhelpful database-level errors.
- **Solution**: Implemented `app.core.geo_validation` module with strict validation functions. Any invalid boundary geometry raises `GeoValidationError` which is converted into a clear 422 Unprocessable Entity response with actionable error details before hitting MongoDB.

## 2. Test Fixture Database Mocking Pattern
- **Problem**: Testing FastAPI endpoints with MongoDB dependencies often causes coupling issues if dependency injection is not uniform.
- **Solution**: Followed the established codebase convention of calling `db = get_database()` inside route handlers and dynamically monkeypatching `get_database` in pytest fixtures (`backend/tests/test_zones.py`) using `AsyncMock` to simulate PyMongo collections.

## 3. Zustand v5 Persist Middleware Typing
- **Problem**: TypeScript compiler threw errors on `create<AuthState>(persist(...))` due to Zustand v5's curried middleware typing requirements.
- **Solution**: Updated `frontend/store/authStore.ts` to use the standard Zustand v5 curried syntax: `create<AuthState>()(persist(...))`.

## 4. Cross-Platform Map Coordinate Compatibility
- **Problem**: Leaflet (web) and `react-native-maps` (native) expect `{ latitude, longitude }` objects, while RFC 7946 GeoJSON delivers `[longitude, latitude]` arrays.
- **Solution**: Added mapping transformations in `TouristMap` and `AdminMap` to convert GeoJSON coordinate tuples into `{ latitude: lat, longitude: lon }` arrays passed into `RealMap`'s enhanced `polygons` prop with risk-level styling.
