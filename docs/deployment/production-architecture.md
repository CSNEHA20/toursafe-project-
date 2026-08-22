# TourSafe Production Architecture & Topology

## Architectural Overview

TourSafe is engineered with a Defense-in-Depth, Zero-Trust multi-tier microservices architecture designed for life-safety reliability, real-time location telemetry processing, and strict DPDP/GDPR compliance.

```
                      +-----------------------------+
                      |   Tourists & Responders     |
                      |   (Mobile App / Web UI)     |
                      +--------------+--------------+
                                     |
                       HTTPS (443) / WSS (TLS 1.3)
                                     |
                                     v
                      +-----------------------------+
                      |     Nginx Gateway / Ingress  |
                      | (Rate Limits, TLS, HSTS)    |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |     TourSafe FastAPI API     |
                      | (Stateless Replicas x3..15) |
                      +-------+--------------+------+
                              |              |
           +------------------+              +------------------+
           | (Pub/Sub, Live Cache)                              | (Durable Records, Audits)
           v                                                    v
+-----------------------+                            +-----------------------+
|   Redis 7.2 In-Memory  |                            |   MongoDB 7.0 Replica |
|  - Live GPS Cache     |                            |  - User Credentials  |
|  - Rate Limit Tokens  |                            |  - Geospatial Zones   |
|  - WebSocket Bus      |                            |  - Immutable Audits   |
+-----------+-----------+                            +-----------+-----------+
            |                                                    |
            +------------------+              +------------------+
                               |              |
                               v              v
                      +-----------------------------+
                      |  Async Workers & ML Engine  |
                      | - LSTM Anomaly Detection    |
                      | - Telemetry Window Decay    |
                      | - Emergency Orchestration   |
                      +-----------------------------+
                                     |
                                     v
                      +-----------------------------+
                      | AWS KMS / Encrypted S3      |
                      | - Private KYC Vault         |
                      | - Encrypted DB Backups      |
                      +-----------------------------+
```

---

## Network Isolation & Zero-Trust Zones

1. **Public Zone (Ingress)**:
   - Only TCP 80 (redirected) and TCP 443 are exposed to the public internet.
   - Cloudflare / AWS WAF filters malicious payloads, DDoS bursts, and scans.
2. **Application Zone (VPC Private Subnet)**:
   - `toursafe-api`, `toursafe-worker`, and `toursafe-ml` execute in isolated private subnets without public IPv4 addresses.
   - Egress traffic routes through NAT Gateways for external notification providers (SMS/Email) and LLM endpoints.
3. **Data Storage Zone (VPC Isolated Subnet)**:
   - `toursafe-mongodb` and `toursafe-redis` bind strictly to internal VPC interfaces (`10.100.20.0/24`).
   - Zero route to internet gateways. Kubernetes NetworkPolicies deny all ingress traffic unless originating from pods with `tier=backend` or `tier=worker` labels.
4. **Storage & Vault Zone**:
   - S3 KYC Identity Vault blocks all public ACLs, requires AWS KMS Customer Managed Keys, and logs all S3 access via CloudTrail.

---

## Data Flow Pipelines

### 1. High-Throughput Mobile Telemetry Flow
```
Mobile GPS/IMU -> Nginx Gateway (/api/v1/telemetry/batch) -> FastAPI Ingestion -> Redis Live State (TTL 120s) -> Async Buffer Queue -> Windowing Engine -> LSTM Inference -> Multi-Signal Risk Assessment -> (if Elevated) State Machine -> Incident Lifecycle -> Command Center WebSocket
```

### 2. Emergency SOS Flow
```
Tourist SOS Button -> WebSocket / REST -> Immediate Priority Escalation -> Redis High-Priority Pub/Sub -> MongoDB Immutable Incident Insert -> Dispatch Orchestration Engine -> Authority Command Center Audio/Visual Alarm -> Responder Field App Push Notification
```
