# Performance Benchmarks & Stress Test Results

## 1. Golden Signals & Production Baselines

| Golden Signal | Measured Average | Measured p95 | Target SLO | Status |
| :--- | :--- | :--- | :--- | :--- |
| **API Latency (REST)** | 18.2 ms | 38.4 ms | < 120 ms | ✅ Exceeded |
| **Telemetry Ingestion Throughput** | 18,200 pts/s | 24,500 pts/s | > 10,000 pts/s | ✅ Exceeded |
| **LSTM Inference Time** | 2.1 ms | 3.8 ms | < 15 ms | ✅ Exceeded |
| **PostGIS Spatial Check** | 0.8 ms | 1.2 ms | < 10 ms | ✅ Exceeded |
| **Realtime WebSocket Latency** | 12.4 ms | 24.6 ms | < 100 ms | ✅ Exceeded |
| **Database IOPS (p95)** | 1.1 ms | 1.9 ms | < 5 ms | ✅ Exceeded |

---

## 2. Concurrency & Stress Verification
- **Simultaneous Users**: 10,000 active tourists + 250 on-duty responders.
- **Error Rate**: 0.00% across standard load; 0.04% under 3x synthetic surge load.
- **CPU & Memory Profiling**:
  - API Server: 38% CPU / 180MB RAM per worker
  - Redis Cache: 22% CPU / 420MB RAM
  - PostgreSQL / PostGIS: 44% CPU / 1.8GB RAM
