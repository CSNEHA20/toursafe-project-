# TourSafe Production Service Inventory

This inventory documents all microservices, background workers, stateful data stores, and proxy layers comprising the TourSafe platform.

| Service Name | Purpose | Runtime | Internal Port | Dependencies | Health Probe | Scaling Strategy | Criticality Tier |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **toursafe-gateway** | Reverse proxy, TLS termination, SSL ciphers, rate limiting, security headers, WebSocket proxy | Nginx 1.27 Alpine | 80, 443 | toursafe-api, toursafe-frontend | HTTP 200 `/health` | Static (2 replicas) | Tier 1 (Critical) |
| **toursafe-api** | Core REST & WebSocket API, Authentication, Incident Management, Geofencing, Compliance, Copilot | Python 3.11 / FastAPI / Uvicorn | 8000 | MongoDB, Redis | `/health/live`, `/health/ready`, `/health/startup` | Horizontal Pod Autoscaler (3-15 replicas on CPU/RAM) | Tier 1 (Life-Safety Critical) |
| **toursafe-worker** | Asynchronous queue worker, telemetry window aggregation, risk decay, audit sync | Python 3.11 | - | Redis, MongoDB | Process PID / Celery/Resilience Queue loop | Queue-depth based (2-8 replicas) | Tier 2 (High) |
| **toursafe-ml** | Real-time LSTM anomaly inference & ML lifecycle management | Python 3.11 / ONNX / NumPy | 8000 / Queue | Redis, Model Registry | `/health/live` | GPU/CPU compute (2-6 replicas) | Tier 2 (High) |
| **toursafe-frontend** | Web client & Authority Command Center SPA | Nginx 1.27 Alpine (Static Expo Web bundle) | 80 | toursafe-gateway, toursafe-api | HTTP 200 `/` | CDN / Static 2 replicas | Tier 2 (High) |
| **toursafe-mongodb** | Primary operational document database & audit repository | MongoDB 7.0 WiredTiger | 27017 | EBS / Persistent Storage | `mongosh ping` | 3-node Replica Set (Primary + 2 Secondaries) | Tier 1 (Critical Data Store) |
| **toursafe-redis** | In-memory cache, WebSocket pub/sub bus, real-time live telemetry buffer, rate limits | Redis 7.2 Alpine | 6379 | Persistent AOF Volume | `redis-cli ping` | Primary-Replica with Sentinel / Cluster | Tier 1 (Critical Realtime Bus) |
| **toursafe-prometheus** | System metrics scraper, SLO/SLI tracking, alerting engine | Prometheus 2.53 | 9090 | toursafe-api `/metrics` | `/healthy` | Single instance with persistent TSDB | Tier 3 (Operational Observability) |

---

## Service Criticality Matrix & Graceful Degradation Tiers

1. **Tier 1 (Life-Safety Critical)**: `toursafe-gateway`, `toursafe-api`, `toursafe-mongodb`, `toursafe-redis`.
   - Failure directly impedes SOS reporting or responder dispatch.
   - Circuit breakers, automated failover, and in-memory fallback buffers ensure no packet drop.
2. **Tier 2 (Operational & Analytics)**: `toursafe-worker`, `toursafe-ml`, `toursafe-frontend`.
   - If ML or analytics worker degrades, the core rule engine continues deterministic threshold safety evaluation without interruption.
3. **Tier 3 (Observability & Reporting)**: `toursafe-prometheus`.
   - Scrapes metrics without impacting transactional throughput.
