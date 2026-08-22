# TourSafe Redis Disaster Recovery Runbook

## 1. Failure Scenarios & Impact
- **Role of Redis**: Ephemeral state caching, real-time WebSocket pub/sub bus, active rate-limiting counters.
- **Resilience Guarantee**: Redis is treated as an auxiliary cache and ephemeral bus. **No safety-critical permanent data exists solely in Redis.**

---

## 2. Recovery Procedures

### Scenario A: Redis Process Crash / Outage
1. Platform automatically switches to `InMemoryFallbackCache` via `redis_resilience_manager`.
2. Critical session tokens and user state continue operating out of local RAM and MongoDB fallback lookups.
3. System logs `REDIS_UNAVAILABLE` warning but remains functional (`status: DEGRADED`).

### Scenario B: Redis Restoration / Restart
1. When Redis reconnects, `redis_resilience_manager.rebuild_ephemeral_state()` is invoked.
2. Active user sessions and emergency telemetry windows are refreshed from MongoDB.
3. `/health/ready` updates from `DEGRADED` to `HEALTHY`.
