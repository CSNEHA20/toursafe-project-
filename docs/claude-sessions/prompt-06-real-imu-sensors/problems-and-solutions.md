# Prompt 6: Problems and Solutions

## Problem 1: Ambiguous `SensorSubscription` Re-Export in `lib/sensors/index.ts`
- **Problem**: `tsc --noEmit` failed with: `error TS2308: Module "./accelerometer" has already exported a member named 'SensorSubscription'. Consider explicitly re-exporting to resolve the ambiguity.`
- **Cause**: Both `accelerometer.ts` and `gyroscope.ts` defined and exported identical `interface SensorSubscription { remove: () => void }`, which collided when `index.ts` performed wildcard re-exports `export * from "./accelerometer"` and `export * from "./gyroscope"`.
- **Solution**: Updated `gyroscope.ts` to import `SensorSubscription` from `./accelerometer` instead of re-declaring an identical exported type.
- **Verification**: `npm run type-check` compiled cleanly with exit code 0.

---

## Problem 2: Bundler Transform Error When Testing Sensor Adapters in Node CLI
- **Problem**: Running `npx tsx --test frontend/tests/imu.test.ts` initially produced `TransformError: Unexpected "typeof"` inside `node_modules/react-native/index.js`.
- **Cause**: Direct top-level imports of `expo-sensors` and `react-native` pulled in native-only React Native code into the Node.js test environment when running headless unit tests.
- **Solution**: Encapsulated native module calls in `AccelerometerAdapter` and `GyroscopeAdapter` with safe dynamic `require("expo-sensors")` lookups and availability checks, allowing mock adapters to execute unit and lifecycle tests in any environment without pulling in native runtime dependencies.
- **Verification**: All 15 frontend unit tests passed in 709 ms.

---

## Problem 3: MongoDB Server Selection Timeout During Pytest Ingestion Test
- **Problem**: Pytest execution on `backend/tests/test_imu.py` timed out after 30 seconds with `ServerSelectionTimeoutError` on `test_ingest_single_sample_success`.
- **Cause**: The endpoint helper `resolve_tourist_id` attempted to query `db["tourists"]` against `localhost:27017` in an offline test environment where local MongoDB service was not running.
- **Solution**: Added `MockAppDatabase` autouse fixture in `backend/tests/test_imu.py` monkeypatching `get_database` in both `db_module` and `imu_router_mod`.
- **Verification**: All 11 backend IMU tests passed in under 1 second.
