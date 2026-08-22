# TourSafe Infrastructure & DevOps Specifications

## Infrastructure Components & Cloud Architecture

TourSafe is containerized and cloud-agnostic, ready for deployment on Kubernetes (EKS, GKE, AKS, or on-premise k8s) or Docker Compose environments.

### 1. Network Topology
- **VPC CIDR**: `10.100.0.0/16`
- **Subnets**:
  - `Public Subnet`: `10.100.1.0/24`, `10.100.2.0/24` (Load Balancers & Ingress Gateway).
  - `Private App Subnet`: `10.100.10.0/24`, `10.100.11.0/24` (API, Worker, ML Inference).
  - `Isolated Data Subnet`: `10.100.20.0/24`, `10.100.21.0/24` (MongoDB Replica Set, Redis Cluster).

### 2. DNS & Domains Configuration
- **Production API Gateway**: `api.toursafe.internal` (or custom registered domain `api.toursafe.org`).
- **Authority Command Center**: `admin.toursafe.internal`.
- **Tourist Web Client**: `app.toursafe.internal`.
- **WebSocket Endpoint**: `wss://api.toursafe.internal/ws`.

### 3. Secret Management & Rotation Strategy
- **JWT Signing Keys**: 256-bit high entropy secret stored in AWS Secrets Manager / Vault. Rotated bi-annually or immediately upon compromise via zero-downtime key rotation mechanism (supporting previous + active keys during grace period).
- **Database Passwords**: Auto-rotated every 90 days via Vault database secrets engine.
- **Provider API Keys (Gemini / Twilio / SMS)**: Injected strictly via environment variables into pod containers; never written to disk or logs.

### 4. Database Resilience & Indexes
- **Engine**: MongoDB 7.0 WiredTiger.
- **Indexes**:
  - Unique indices on `tourists.email`, `users.id`, `incidents.id`.
  - 2dsphere Geospatial indices on `zones.boundary`, `zones.center`, `location_history.location`, `telemetry_samples.location`.
  - Compound indices on `(tourist_id, timestamp DESC)` for real-time temporal queries.
- **Connection Pooling**: Min 10, Max 100 connections per API pod. Server selection timeout capped at 5000ms.

### 5. Redis In-Memory Architecture
- **Engine**: Redis 7.2 Alpine.
- **Memory Policy**: `volatile-lru` (Caps max memory to 512MB/1GB per instance; expires stale telemetry buffers and session tokens while guaranteeing persistent pub/sub and queue safety).
- **Persistence**: Append-Only File (`AOF`) with `fsync everysec` for durable recovery.
