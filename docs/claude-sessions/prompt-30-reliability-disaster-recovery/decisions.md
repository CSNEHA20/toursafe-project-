# Architectural Decisions — Prompt 30

## Key Architectural Decisions

1. **Strict Separation of Life-Safety Paths from Auxiliary Compute**:
   - **Decision**: Auxiliary compute (AI Copilot, LSTM Anomaly Forecasting, Analytic Heatmaps) must never block or degrade SOS reception, incident creation, or responder tasking.
   - **Implementation**: Under high system load or in `CRITICAL_ONLY` mode, the `require_priority_allowance` guard fast-fails non-critical requests with HTTP 503 while critical operations receive dedicated execution priority.

2. **Realistic SLOs vs. Theoretical Guarantees**:
   - **Decision**: Avoided claiming "99.99% multi-region zero-downtime" on a single-region deployment.
   - **Implementation**: Published empirical SLOs (99.9% API availability, 99.99% SOS ingestion, p95 latency ≤ 250ms) measured continuously in code.

3. **Ephemeral Role of Redis**:
   - **Decision**: No permanent safety-critical data is allowed to reside exclusively in Redis.
   - **Implementation**: Redis outages trigger `InMemoryFallbackCache` and direct MongoDB fallback; state is reconstructed upon reconnection.

4. **Multi-Tier Health Probes**:
   - **Decision**: Separated liveness from readiness to avoid cascading container kill loops during downstream DB slowdowns.
   - **Implementation**: `/health/live` performs a non-cascading process check; `/health/ready` evaluates dependency readiness.

5. **Operational vs. Technical Observability Separation**:
   - **Decision**: Authority operators in the command center should not be overwhelmed with raw Redis memory or CPU graphs.
   - **Implementation**: Authority operators receive a consolidated `OperationalHealthBar` with human-readable statuses (e.g. "Location Updates Delayed"), while system administrators have the full `ReliabilityDashboard`.
