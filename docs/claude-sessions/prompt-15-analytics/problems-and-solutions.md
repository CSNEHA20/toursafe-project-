# Prompt 15 Problems and Solutions

## 1. GPS Travel Distance Distortion from Stationary Noise & Jumps
- **Problem**: Blindly summing Euclidean/Haversine coordinate differences between consecutive GPS samples resulted in substantial artificial distance inflation when tourists were stationary (GPS jitter of 2-5m every 5s) and massive spikes during tunnel exits (GPS jumps).
- **Cause**: GPS receivers produce subtle Gaussian noise when stationary and occasional multi-kilometer multipath jumps upon satellite reconnection.
- **Solution**: Implemented a 3-tier filter in `calculate_travel_distance_km`:
  1. Skip samples with accuracy $> 100\text{m}$.
  2. Skip distance accumulation when movement is within the stationary noise floor ($\Delta d < 2\text{m}$).
  3. Reject speed jumps exceeding plausible vehicular limits ($v > 70\text{ m/s} \approx 252\text{ km/h}$).
- **Verification**: Verified in `test_gps_distance_with_noise_and_jump_rejection` fixture.

---

## 2. Frontend API Client Mock Signature Conflict
- **Problem**: When replacing `analyticsApi` in `frontend/lib/api.ts` with new real endpoints, TypeScript reported errors in `useMockApi.ts` where old stub functions (`getKPIs`, `getIncidentTrends`) were expected.
- **Cause**: Earlier MVP components still referenced legacy stub names.
- **Solution**: Maintained backward-compatible aliases for legacy function names while providing complete mock fallback data for all 14 new real endpoints.
- **Verification**: `npm run type-check` and `npm run lint` passed with 0 errors.

---

## 3. Date Span Query Exhaustion Risk
- **Problem**: Unbounded client requests (e.g. asking for 5 years of hourly data) could exhaust server RAM and MongoDB cursor connections.
- **Cause**: Defaulting to client-specified date ranges without safety limits.
- **Solution**: Implemented `normalize_time_range` with maximum span clamping (30 days for hourly, 90 days for daily, 365 days for monthly).
- **Verification**: Verified in `test_time_normalization_and_bounding` unit test.
