# Prompt: Backend Foundation - TourSafe Authentication

## Objective
Establish the real backend foundation for the TourSafe project by creating a FastAPI backend with MongoDB persistence, real JWT authentication with Argon2id password hashing, role-based authorization, and integrate the existing React Native frontend with the new authentication system - while removing production dependency on mock authentication.

## Important Details
- Project structure: React Native/Expo frontend + FastAPI backend + MongoDB
- Authentication flow: Frontend login/register → FastAPI auth endpoints → JWT tokens → React Native authStore → route protection
- Key constraints: Preserve existing UI/screens, no AI/telemetry/geo-fencing/blockchain implementations, use Argon2id for password hashing, role must come from persisted data not email inference
- Mock auth removal: Supabase mock client must not be production default; EXPO_PUBLIC_USE_MOCK must be explicitly opt-in
- Development flag: EXPO_PUBLIC_DEV_BYPASS exists but real auth must be default path

## Work State

### Completed
- FastAPI backend directory structure created at `backend/` with modular app layout
- `app/main.py` - FastAPI entry point with CORS middleware and router inclusion
- `app/core/config.py` - Pydantic-settings with MongoDB URI, JWT secrets, CORS origins
- `app/core/database.py` - Motor async MongoDB connection layer
- `app/core/security.py` - Argon2id password hashing, JWT token creation/decoding
- `app/models/user.py` - User model with UUID IDs, email uniqueness, to_dict/from_dict
- `app/models/tourist.py` - Tourist profile model linked to User
- `app/models/authority.py` - Authority profile model linked to User
- `app/schemas/user.py` - Pydantic schemas for registration, login, tokens, profiles
- `app/routers/auth.py` - Auth endpoints: register, login, refresh, logout, me with role protection
- `app/routers/tourists.py` - Tourist profile endpoints with role gating
- `app/routers/authority.py` - Authority profile endpoints with verification status
- Environment files: `backend/.env.example` with all required variables
- Frontend `lib/api.ts` updated with token refresh logic and 401 handling
- Frontend `store/authStore.ts` updated with JWT-based session management using AsyncStorage
- Frontend auth screens (login.tsx, register.tsx, select-role.tsx) updated to call FastAPI endpoints
- Frontend `lib/supabase.ts` updated: mock auth explicitly opt-in via EXPO_PUBLIC_USE_MOCK, production uses FastAPI
- `backend/tests/test_auth.py` - Comprehensive test suite scaffolded (15 test cases)
- `backend/requirements.txt` with all Python dependencies
- npm type-check passes, lint passes (pre-existing warnings only)

### Active
- Backend test execution - pytest collection errors due to dependency override issues with async get_database; need to resolve mocking strategy
- Frontend verification - need to run Expo app with FastAPI backend to confirm tourist/authority registration/login flows
- Authority verification status flow - verification_update endpoint needs testing
- CORS configuration with dynamic origins from environment

### Blocked
- Backend tests failing due to `get_database()` returning coroutine in synchronous TestClient context - need to fix mock database strategy (currently using patch but override not applying correctly)
- Full end-to-end verification requires running MongoDB + backend + Expo app simultaneously

## Next Move
1. Fix backend test mocking strategy - either use async pytest with asyncio, switch to synchronous Motor mock, or use unittest.mock.patch correctly on the imported get_database function
2. Start FastAPI backend server: `cd backend && uvicorn app.main:app --reload`
3. Start Expo app: `npm start` then test auth flows manually
4. Verify: tourist registration, tourist login, auth persistence after restart, authority registration, route protection (tourist cannot access authority endpoints)
5. Run full test suite and fix any remaining failures

## Relevant Files
- `backend/app/main.py` - FastAPI app entry, CORS, router inclusion
- `backend/app/core/config.py` - Settings with env var parsing
- `backend/app/core/database.py` - Motor MongoDB connection
- `backend/app/core/security.py` - Argon2id hashing, JWT functions
- `backend/app/models/user.py` - User model with UUID IDs
- `backend/app/models/tourist.py` - Tourist profile model
- `backend/app/models/authority.py` - Authority profile model  
- `backend/app/schemas/user.py` - Pydantic schemas
- `backend/app/routers/auth.py` - Auth endpoints with role protection
- `backend/app/routers/tourists.py` - Tourist endpoints
- `backend/app/routers/authority.py` - Authority endpoints
- `backend/.env.example` - Environment variables template
- `backend/tests/test_auth.py` - Test suite (15 cases)
- `toursafe-react/store/authStore.ts` - Redux store with JWT session
- `toursafe-react/lib/api.ts` - Axios client with token refresh
- `toursafe-react/app/auth/login.tsx` - Login form calling FastAPI
- `toursafe-react/app/auth/register.tsx` - Authority registration calling FastAPI
- `toursafe-react/app/auth/select-role.tsx` - Role selection screen
- `toursafe-react/lib/supabase.ts` - Mock auth isolated, production default disabled
- `toursafe-react/.env.example` - Frontend env vars (API URL, WS URL, dev bypass, mock flag)