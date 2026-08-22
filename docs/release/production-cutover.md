# TourSafe — Production Cutover & Deployment Strategy

## 1. Cutover Architecture & Strategy
TourSafe employs a zero-downtime **Blue/Green Deployment Strategy with Canary Validation** for release cutover.

```
       [ Client Ingress (DNS / Cloudflare) ]
                         |
           [ Ingress Traffic Router ]
             /                    \
     (95% Traffic)           (5% Canary Traffic)
          |                           |
   [ Blue Cluster (Active) ]     [ Green Cluster (v1.0.0-rc1) ]
          \                           /
           \                         /
         [ MongoDB 7.0 / Redis 7.2 Core Cluster ]
```

---

## 2. Step-by-Step Cutover Timeline

| Time Offset | Phase | Operational Actions | Success Criteria |
| :--- | :--- | :--- | :--- |
| **$T - 60\text{m}$** | Pre-Flight | Run `python -m pytest backend/tests` & verify zero failures. | 515/515 Tests Passed |
| **$T - 45\text{m}$** | Backup | Trigger point-in-time snapshot backup drill. | Backup Archive Verified |
| **$T - 30\text{m}$** | Green Deploy | Deploy v1.0.0-rc1 containers to Green target environment. | `/health/live` & `/health/ready` 200 OK |
| **$T - 15\text{m}$** | Smoke Test | Run `python scripts/synthetic_smoke_test.py` on Green. | 100% Synthetic Pass |
| **$T - 05\text{m}$** | Canary Route | Route 5% live traffic to Green cluster. | Error rate $< 0.01\%$, P95 Latency $< 200\text{ms}$ |
| **$T + 00\text{m}$** | Full Cutover | Shift 100% traffic to Green cluster (Promote to Active). | All WS & REST traffic healthy |
| **$T + 15\text{m}$** | Post-Flight | Monitor golden signals, error rates, and connection pool. | CPU $< 40\%$, RAM $< 50\%$, 0 restarts |
| **$T + 60\text{m}$** | Standby Ret | Keep Blue cluster warm in standby for 2 hours before teardown. | Rollback readiness confirmed |

---

## 3. Abort Triggers & Automatic Rollback Gates
Traffic is automatically reverted to the Blue cluster if any of the following occur during the 15-minute canary or immediate cutover window:
1. HTTP 5xx error rate exceeds $0.5\%$ over a 60-second window.
2. P95 API response latency exceeds $500\text{ms}$.
3. Emergency SOS ingestion fails to create an incident record within 1000ms.
4. WebSocket heartbeat dropped connection count exceeds $5\%$ of total connected clients.
