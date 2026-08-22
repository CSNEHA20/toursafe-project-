# TourSafe — Production Release Runbook

## 1. Role & Responsibility Assignment
- **Release Commander**: Lead DevOps Engineer (Oversees cutover sequence and abort calls).
- **Backend Lead**: Verifies API endpoints, database health, and background worker queues.
- **Frontend / Mobile Lead**: Monitors mobile client telemetry ingestion and WebSocket push feeds.
- **Authority Liaison**: Monitors simulated authority emergency response acknowledgment.

---

## 2. Release Commands & Execution Steps

### 2.1 Pre-Release Sanity Checks
```bash
# 1. Verify all automated unit, integration, and regression suites
python -m pytest backend/tests -v

# 2. Verify frontend TypeScript type correctness
npm --prefix frontend run type-check

# 3. Verify disaster recovery backup integrity
python scripts/backup_restore_drill.py
```

### 2.2 Container Build & Staging Push
```bash
# Build and tag release container
docker build -t ghcr.io/toursafe/backend:1.0.0-rc1 -f backend/Dockerfile backend/

# Push to container registry
docker push ghcr.io/toursafe/backend:1.0.0-rc1
```

### 2.3 Kubernetes / Production Rolling Update
```bash
# Apply release deployment manifest
kubectl apply -f infra/k8s/production/deployment.yaml

# Monitor rollout status
kubectl rollout status deployment/toursafe-backend -n toursafe-prod --timeout=300s
```

### 2.4 Production Health Probes & Post-Deploy Verification
```bash
# Check liveness and readiness probes
curl -f https://api.toursafe.io/health/live
curl -f https://api.toursafe.io/health/ready

# Run synthetic smoke test against production target
ENVIRONMENT=production python scripts/synthetic_smoke_test.py
```
