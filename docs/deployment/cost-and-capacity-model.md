# TourSafe Capacity Planning & Cost Drivers Model

This model provides estimated resource requirements, throughput targets, and major cost drivers for operating TourSafe at scale.

## Capacity Dimension Model

| Metric / Dimension | Baseline (10,000 Active Tourists) | High Peak (100,000 Active Tourists) | Critical Event (500,000 Active Tourists) |
| :--- | :--- | :--- | :--- |
| **Telemetry Ingestion Rate** | ~500 samples/sec (50Hz windowed) | ~5,000 samples/sec | ~25,000 samples/sec |
| **Concurrent WebSocket Connections** | ~8,000 | ~75,000 | ~350,000 |
| **API Requests (REST)** | ~150 req/sec | ~1,200 req/sec | ~6,000 req/sec |
| **Incidents / Day (Average)** | 5 - 20 | 50 - 200 | 500 - 2,000 |
| **API CPU Allocation** | 4 vCPU (2 pods) | 24 vCPU (12 pods) | 80 vCPU (40 pods) |
| **API RAM Allocation** | 4 GB | 24 GB | 80 GB |
| **MongoDB RAM Allocation** | 8 GB (M30) | 32 GB (M50) | 64 GB (M60+) |
| **Redis RAM Allocation** | 2 GB | 8 GB | 32 GB Cluster |

---

## Major Cost Drivers & Optimization Levers

1. **Telemetry Ingestion & Storage**:
   - **Cost Driver**: Continuous 50Hz sensor data (GPS + IMU) generates ~50MB per tourist per day.
   - **Optimization**: Dynamic sampling rate decay (drops to 10Hz when stationary, increases to 50Hz upon motion/anomaly). Aggressive 30-day retention with automated TTL expiration in MongoDB.
2. **AI Copilot & LLM Token Usage**:
   - **Cost Driver**: Authority queries, RAG context lookups, and incident summaries.
   - **Optimization**: Strict bounded context window (max 2048 tokens), tool response caching, and rate limiting (max 10 copilot prompts/min per operator).
3. **Map Tiles & Geocoding**:
   - **Cost Driver**: Map tile rendering on mobile clients and Authority Command Center.
   - **Optimization**: Client-side tile caching and OpenStreetMap/Vector tile self-hosting.
4. **Emergency SMS & Voice Notifications**:
   - **Cost Driver**: Outbound SMS / WhatsApp alerts via Twilio/AWS SNS during widespread safety alerts.
   - **Optimization**: Push notifications via Expo/FCM prioritized as zero-cost primary channel; SMS reserved strictly for high-severity SOS escalations.
