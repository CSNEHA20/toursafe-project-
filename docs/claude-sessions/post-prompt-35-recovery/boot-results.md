# Boot Results — TourSafe Frontend & Backend

## Frontend Boot Status
- **Command Used**: `npx expo start --web --clear`
- **Host / URL**: `http://localhost:8081`
- **Bundler**: Metro (Expo SDK 52)
- **Status**: RUNNING
- **Bundle Generation**:
  - Total Modules Bundled: 2875 modules
  - Bundle Size: 12,069,397 bytes
  - Initial Bundle Time: ~8.8s
- **Route Accessibility**:
  - `/` (Home Portal): HTTP 200 OK
  - `/auth/login` (Authentication): HTTP 200 OK
  - `/tourist/(tabs)/dashboard` (Tourist Dashboard): HTTP 200 OK
  - `/admin/(tabs)/dashboard` (Authority Command Center): HTTP 200 OK
  - `/responder` (Tactical Field Responder): HTTP 200 OK

## Backend Boot Status
- **Command Used**: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Host / URL**: `http://localhost:8000`
- **Framework**: FastAPI / Starlette
- **Status**: RUNNING
- **Probes Verified**:
  - `/health/live`: HTTP 200 OK (`{"status": "HEALTHY", "uptime_seconds": 20.89}`)
  - `/health`: HTTP 200 OK (`{"status": "unavailable", "mode": "FULL", "services": {"backend": {"status": "healthy"}}}`)
