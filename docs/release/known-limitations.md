# TourSafe — Known Limitations & Operational Boundaries

## 1. Known Architectural Limitations (v1.0.0-rc1)

1. **GPS Kinematic Precision in Severe Dense Urban/Canopy Canyons**:
   - In environments where GPS Dilution of Precision ($\text{DOP} > 5.0$) or accuracy radius $> 50\text{m}$, the system falls back to geohash bounding and historical trajectory prediction.
   - *Mitigation*: Multi-modal IMU step-counting and dead-reckoning fusion active on client devices.

2. **Simulated Sandbox Load Caps**:
   - The in-memory policy simulation sandbox supports up to 10,000 synthetic entities simultaneously per worker node. Larger stress simulations require distributed batching.

3. **External SMS Delivery Provider Latency**:
   - In rare telecom congestion events, SMS gateways may introduce $5\text{--}15\text{s}$ delivery delays.
   - *Mitigation*: TourSafe uses active in-app Push Notifications as primary dispatch with dual-carrier SMS fallback.
