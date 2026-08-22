# TourSafe Production Runbook & Operations Guide

This runbook guides Site Reliability Engineers (SREs) and Operations personnel in operating, maintaining, and troubleshooting TourSafe in production.

## 1. System Startup & Bootstrap Procedure

### Docker Compose Environment
```bash
# 1. Start foundational state stores (MongoDB & Redis)
docker compose up -d mongodb redis

# 2. Apply database forward migrations
python scripts/migrate.py up

# 3. Bootstrap root authority administrator (if initial setup)
python scripts/bootstrap_admin.py --email ops-admin@toursafe.internal

# 4. Start API, workers, ML engine, and reverse proxy
docker compose up -d backend worker ml_service frontend reverse_proxy prometheus
```

### Kubernetes Environment
```bash
# 1. Apply namespace, secrets, and configurations
kubectl apply -k infra/k8s/base/

# 2. Monitor rollout status
kubectl rollout status deployment/toursafe-api -n toursafe --timeout=120s
```

---

## 2. Health Monitoring & Triage

| Endpoint | Target Consumer | Expected Response | Failure Action |
| :--- | :--- | :--- | :--- |
| `GET /health/live` | K8s Liveness Probe | `{"status":"HEALTHY"}` (200 OK) | Restart pod if unresponsive |
| `GET /health/ready` | K8s Readiness Probe | `{"status":"HEALTHY","ready":true}` | Remove pod from traffic router |
| `GET /health/startup` | K8s Startup Probe | `{"status":"HEALTHY","database_connected":true}` | Wait for DB initialization |
| `GET /metrics` | Prometheus Scraper | Prometheus text metrics | Check metrics exporter |

---

## 3. Emergency Incident Response & Troubleshooting

### Scenario A: High API Error Rate (HTTP 5xx Spikes)
1. Check Nginx gateway logs: `docker logs toursafe_gateway --tail 100` or `kubectl logs -l app=ingress-nginx`.
2. Inspect backend logs for unhandled exceptions: `kubectl logs -l app=toursafe-api --tail 200`.
3. Check database connectivity: run `./scripts/health-check.sh`.
4. If a regression is detected in the latest deployment, initiate immediate rollback: `./scripts/rollback.sh production previous "Elevated 5xx error rate"`.

### Scenario B: Redis Outage / Memory Pressure
1. Check Redis memory usage: `redis-cli -a <pass> info memory`.
2. Verify that `volatile-lru` eviction is active so live queues are not dropped.
3. If Redis crashes, TourSafe automatically activates in-memory degraded mode, continuing SOS and critical triage without interruption.

### Scenario C: High Telemetry Ingestion Queue Backlog
1. Scale up worker pods: `kubectl scale deployment toursafe-worker --replicas=6 -n toursafe`.
2. Verify consumer lag in Redis queues.
