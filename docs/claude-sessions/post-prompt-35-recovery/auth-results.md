# Authentication Results — TourSafe

## Authentication Configuration
- **Auth Store**: Zustand `useAuthStore` with persistent storage via `AsyncStorage` (`toursafe-auth`).
- **Endpoints**:
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/refresh`
  - `GET /api/v1/auth/me`
- **JWT Lifetimes**:
  - Access Token: 30–60 minutes
  - Refresh Token: 7 days

## Mock vs Real Backend Policy
- `EXPO_PUBLIC_USE_MOCK=false`: Disabled by default for standard development.
- `EXPO_PUBLIC_DEV_BYPASS=false`: Disabled by default so real authentication flow executes.

## Interceptors & Recovery
- `frontend/lib/api.ts` Axios interceptor attaches `Authorization: Bearer <token>` to all authenticated requests.
- Automatic 401 interceptor initiates token refresh via `POST /api/v1/auth/refresh` without losing queued concurrent requests.
- On refresh expiration, safely clears storage and redirects to `/auth/login`.
