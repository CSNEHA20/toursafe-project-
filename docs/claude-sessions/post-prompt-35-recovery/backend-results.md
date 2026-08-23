# Backend Results — TourSafe FastAPI

## Server Information
- **Framework**: FastAPI (Python 3.14 on Windows)
- **ASGI Server**: Uvicorn 0.32.0
- **Host / Port**: `0.0.0.0:8000` (`http://localhost:8000`)
- **Active Environment**: `development`

## Probes & Endpoint Validation
1. **Liveness Probe**:
   - `GET /health/live`
   - Response: `200 OK`
   - Payload: `{"status": "HEALTHY", "uptime_seconds": 20.89}`
2. **General Health Probe**:
   - `GET /health` / `GET /api/v1/health`
   - Response: `200 OK`
   - Payload:
     ```json
     {
       "status": "unavailable",
       "mode": "FULL",
       "services": {
         "backend": {
           "status": "healthy",
           "version": "1.0.0",
           "build_sha": "unknown",
           "environment": "development"
         },
         "mongodb": {
           "status": "UNAVAILABLE",
           "latency_ms": null
         },
         "redis": {
           "status": "DISABLED",
           "fallback_active": true
         },
         "realtime": {
           "status": "healthy",
           "transport": "websocket",
           "active_connections": 0,
           "unique_users": 0,
           "active_channels": 0
         }
       }
     }
     ```

## Startup Resilience
- The backend application initializes safely and handles degraded or starting database/cache tiers without application crash.
- CORS origins configured to accept all local development origins (`http://localhost:8081`, `http://127.0.0.1:8081`, `http://localhost:8082`, etc.).
