# Known Limitations — TourSafe Post-Prompt-35

1. **Local MongoDB & Docker Daemon Availability**:
   - In environments without a running local MongoDB instance or Docker daemon, the backend operates in degraded mode (`status: "unavailable"`, mode: `FULL`). The FastAPI application boots, exposes all health probes, and accepts requests, returning informative status codes when querying empty databases.
2. **Browser Subagent Driver CDN Availability**:
   - The automated Playwright headless browser tool experienced an external 404 CDN failure when fetching driver binaries. Verified localhost web bundle delivery via direct HTTP and bundle ingestion scripts with 100% success.
3. **Mobile-Specific Hardware APIs on Web**:
   - Accelerometer and Gyroscope hardware telemetry sensors use web-safe fallbacks on desktop browsers and require physical devices or mobile simulators for continuous raw IMU sampling.
