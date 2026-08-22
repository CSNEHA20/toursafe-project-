# TourSafe Graceful Degradation & Resilience Matrix

## 1. Degradation Modes

1. **`FULL`**: All services running normally with full generative AI copilot, real-time heatmaps, predictive anomaly modeling, and multi-channel notifications.
2. **`DEGRADED`**: Minor downstream slowdown or outage; non-critical background jobs (e.g. historical forecasts) paused; fallback caches and secondary provider routes active.
3. **`CRITICAL_ONLY`**: Platform experiencing extreme CPU, memory, or database pressure. System sheds AI Copilot, analytics aggregations, and decorative visualizations to guarantee 100% capacity for SOS, Incident lifecycle, responder dispatch, and telemetry ingestion.
4. **`OFFLINE`**: Emergency maintenance or network severance; clients operate in local cache/offline buffer mode.

---

## 2. Comprehensive Subsystem Degradation Matrix

| Subsystem | Failure Condition | Impact | Available Functionality | Disabled / Shed Functionality | Recovery Trigger |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Generative AI Copilot** | LLM API timeout / 5xx / Rate limit | Copilot chat unresponsive | Manual dispatch, predefined SOPs, standard incident workflows | Automated summary generation, natural language queries | Circuit breaker half-open trial success |
| **LSTM Anomaly Model** | ONNX/PyTorch engine crash / OOM | ML inference offline | Deterministic safety rule engine, SOS triggers, geofence breaches | Multi-dimensional predictive anomaly scoring | Model reload / fallback to baseline heuristic |
| **Redis Cache / PubSub** | Redis connection refused / timeout | Cache miss, PubSub failure | All CRUD operations via MongoDB direct queries, in-memory rate limits | Ephemeral PubSub acceleration, cached session fast-path | Ephemeral state rebuilder on reconnect |
| **Push Gateway (FCM)** | Google FCM outage / quota exceeded | Mobile push undelivered | SMS notification fallback, direct WebSocket active socket delivery, email alerts | Native push notifications | Notification provider retry & fallback circuit reset |
| **External Weather / Maps API** | Third-party provider down | Weather overlay missing | Native OpenStreetMap cache, static maps, emergency routing | Dynamic weather risk scoring, live traffic overlays | Secondary adapter fallback |
| **Database IOPS Saturation** | MongoDB query latency > 500ms | General API latency elevation | SOS ingestion, incident creation, dispatch updates (via write queues) | Batch analytics reports, tourist history exports, audit search | Load shedding of heavy queries; index optimization |
| **Mobile Client Disconnected** | Cellular network dead zone | Telemetry stream interrupted | Local device buffer, offline geofence check, local SOS alarm queue | Real-time command center sync | Automatic reconnect sync with deduplication & clock reconciliation |

---

## 3. Critical-Only Mode Activation Guide

### Automatic Trigger Conditions
- Database query latency p95 > 350ms for 3 consecutive minutes.
- Process memory utilization > 85%.
- Core incident queue depth > 2,000 pending items.

### Manual Operator Override
Authorized command center administrators can toggle `CRITICAL_ONLY` via the Admin Reliability Dashboard or via API:
```bash
curl -X POST https://api.toursafe.io/api/v1/reliability/degradation/mode \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"mode": "CRITICAL_ONLY", "reason": "Mass casualty incident in Sector 4 - shedding auxiliary compute"}'
```
