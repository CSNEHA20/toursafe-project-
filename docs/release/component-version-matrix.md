# TourSafe — Component Version Matrix

## 1. Component Compatibility & Version Grid

| Component / Subsystem | Repository Path | Version | Minimum Supported Client | Protocol / Interface Contract |
| :--- | :--- | :--- | :--- | :--- |
| **Backend Core Engine** | `backend/` | `1.0.0-rc1` | `1.0.0` | FastAPI / OpenAPI 3.1.0 |
| **Realtime Event Bus** | `backend/app/services/realtime/` | `1.0.0` | `1.0.0` | WebSocket JSON Envelope v1 |
| **Safety & Risk Fusion Engine** | `backend/app/services/safety/` | `1.3.0` | Internal Core | Python 3.11 / 3.14 Async |
| **Emergency Orchestrator** | `backend/app/services/emergency/`| `1.2.0` | Internal Core | Incident State Machine v1 |
| **Authority AI Copilot** | `backend/app/services/copilot/` | `1.1.0` | `1.0.0` | RAG / Tool Registry Contract v1 |
| **Governance & Configuration** | `backend/app/services/authority/`| `1.0.0` | `1.0.0` | SoD & Audit Hash Chain v1 |
| **Tourist Mobile App** | `frontend/` (Expo App) | `1.0.0` | Android $\ge 11$, iOS $\ge 15$ | HTTPS REST + WSS |
| **Authority Command Center** | `frontend/` (Web App) | `1.0.0` | Chrome $\ge 115$, Firefox $\ge 115$ | React 18 / Tailwind / WebSocket |
| **Responder Field App** | `frontend/` (PWA / Mobile) | `1.0.0` | Modern Mobile Browsers | Offline SQLite + Batch Sync v1 |
| **ML Inference Models** | `models/` | `1.2.0` | ONNX Runtime $\ge 1.16$ | Tensor $(B, 6, 128)$ Float32 |

---

## 2. Infrastructure Version Baseline

| Infrastructure Service | Target Engine / Image | Configuration Baseline | Clustering & HA Mode |
| :--- | :--- | :--- | :--- |
| **Primary Database** | MongoDB 7.0.8 | Replica Set (3-node: 1 Primary, 2 Secondary) | Write Concern `majority`, Journaling Enabled |
| **In-Memory Cache / Bus** | Redis 7.2.4 | Redis Sentinel (3-node Sentinel, 1 Master, 2 Replica) | Append Only File (AOF) `everysec` |
| **Reverse Proxy / Ingress** | Nginx 1.25 / Traefik 3.0 | TLS 1.3 Strict, HTTP/2, WebSocket Upgrade | Multi-Instance Load Balanced with Health Probes |
| **Container Runtime** | Docker 26.1 / Kubernetes 1.29 | Rootless, Resource Quotas (CPU: 2 Core, RAM: 4GiB) | Rolling Update Strategy (`maxSurge: 25%`, `maxUnavailable: 0`) |
