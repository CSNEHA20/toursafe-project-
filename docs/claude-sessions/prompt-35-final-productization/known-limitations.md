# Known Limitations & Operating Boundaries

## 1. Documented Operating Boundaries

1. **Cellular Blackout Geographies**:
   - In deep mountain ravines without 2G/4G/5G cellular signals, real-time WebSocket telemetry ingestion falls back to local SQLite offline buffering. Emergency SOS triggers attempt immediate SMS broadcast through emergency satellite or base tower roaming.
2. **GPS Accuracy Degradation Under Dense Forest Canopy**:
   - In heavy canopy areas (e.g. Western Ghats rainforest corridors), GPS dilution of precision (HDOP) may increase beyond 15 meters. The system utilizes dead-reckoning IMU Kalman filtering to bridge GPS micro-dropouts.
3. **Continuous 50Hz IMU Battery Consumption**:
   - Continuous 50Hz accelerometer and gyroscope sampling on legacy mobile hardware can impact battery life. TourSafe applies adaptive mobile edge downsampling (10Hz during static dwell periods, dynamically scaling to 50Hz upon detecting rapid kinematic motion).
4. **Third-Party CAD Integration Latencies**:
   - Webhook dispatches to external 112/NDRF CAD systems depend on external agency network uptime. TourSafe enforces circuit breakers with exponential backoff and a 100-event durable dead-letter queue.
