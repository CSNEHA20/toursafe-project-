# Prompt 34 — Known Limitations

## 1. Documented System Boundaries
1. **Canopy / Urban Canyon GPS Jitter**: Degraded GPS fixes fall back to geohash proximity and client-side IMU dead reckoning.
2. **Policy Sandbox In-Memory Scale**: Single-node simulation sandbox max capacity is 10,000 concurrent entities.
3. **SMS Gateway Telco Latency**: In-app push notifications serve as the primary critical dispatch mechanism with SMS fallback.
