# Failure Tests & Simulation Report — Prompt 30

## Failure Test Scenarios Executed

1. **Transient MongoDB Read/Write Timeout Failure**:
   - **Simulation**: Injected `asyncio.TimeoutError` on the first 2 database attempts.
   - **Result**: Bounded exponential backoff with jitter retried and succeeded on attempt 3. `status: SUCCESS`, zero data dropped.

2. **Redis Cache Outage & Network Partition**:
   - **Simulation**: Disconnected Redis client and issued key-value read/write commands.
   - **Result**: Automatic fallback to `InMemoryFallbackCache`. Key stored and retrieved successfully. `/health/ready` reported `status: DEGRADED` while core API remained operational.

3. **Out-of-Order Event State Regression**:
   - **Simulation**: Dispatched stale out-of-order event attempting to regress an incident from `RESOLVED` back to `OPEN`.
   - **Result**: State machine rejected transition (`regression_blocked: True`), preserving data integrity.

4. **Duplicate SOS Alarm Flood Burst**:
   - **Simulation**: Fired a burst of 50 identical SOS alarm payloads with the same device sequence ID.
   - **Result**: Idempotency guard accepted exactly 1 alarm and deduplicated 49 duplicate payloads.

5. **Load-Shedding Under System Degradation (`CRITICAL_ONLY` Mode)**:
   - **Simulation**: Switched mode to `CRITICAL_ONLY` and submitted simultaneous requests for critical dispatch vs non-critical AI Copilot.
   - **Result**: Critical dispatch succeeded immediately; AI Copilot was rejected early with HTTP 503 (`SERVICE_DEGRADED_LOAD_SHEDDING`), shedding CPU load.
