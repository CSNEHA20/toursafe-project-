# Prompt 7: Real Telemetry Ingestion + Storage Pipeline

```text
TOURSAFE — PROMPT 7
REAL TELEMETRY INGESTION + STORAGE PIPELINE
IMU + GPS TELEMETRY
REALTIME INGESTION
REDIS LIVE STATE
MONGODB PERSISTENCE
TELEMETRY WINDOWS
DATA QUALITY
BACKPRESSURE
OFFLINE BUFFER FOUNDATION

STRICT SCOPE:
DO NOT implement:
- LSTM training
- LSTM inference
- anomaly detection
- anomaly scoring
- fall detection
- geo-fence entry/exit detection
- automatic SOS
- emergency dispatch
- DID
- blockchain
- IPFS
- e-FIR
- responder routing
- FCM

The telemetry pipeline must produce TelemetryWindow which the future AI service will consume.

Mandatory Deliverables:
- Canonical Telemetry Contract (gps.sample, imu.sample, telemetry.sample, telemetry.window)
- Ingestion Pipeline with 15-step processing
- Sequence Management & Idempotency
- Redis Live State with TTL and degraded fallback
- MongoDB Durable Persistence for samples, windows, sessions
- 3-Second Telemetry Window Engine (50 Hz, 150 samples nominal, >=0.6 completeness, max gap <=250ms)
- Multi-Metric Data Quality Evaluation
- Bounded Backpressure Queue
- Mobile Offline Buffering Foundation with Replay
- Authority Operational View with strict privacy guarantees
- Comprehensive Test Suite
- docs/telemetry-architecture.md
- docs/claude-sessions/prompt-07-telemetry-pipeline/
```
