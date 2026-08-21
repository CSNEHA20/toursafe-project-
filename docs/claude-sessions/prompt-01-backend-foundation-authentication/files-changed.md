# Files Changed: Backend Foundation Authentication

## Backend Files

### `backend/app/main.py`
- Fixed router inclusion: changed `app.include_router(auth_router, prefix="/api/v1")` to `app.include_router(auth_router)` 
- Same fix for tourists and authority routers
- This resolved double-prefix issue: `/api/v1/api/v1/auth/register` → `/api/v1/auth/register`

### `backend/app/core/config.py`
- Pydantic-settings with environment variable parsing
- CORS origins configured from `EXPO_PUBLIC_CORS_ORIGINS` env var
- MongoDB URI from `MONGODB_URI` env var
- JWT secrets from `JWT_SECRET_KEY` env var

### `backend/app/core/database.py`
- Motor async MongoDB connection using `AsyncIOMotorClient`
- `get_database()` async function returning database instance
- `close_database()` function to close MongoDB client connection

### `backend/app/core/security.py`
- Argon2id password hashing via `hash_password()` and `verify_password()`
- JWT token creation via `create_access_token()` and `create_refresh_token()`
- JWT token decoding via `decode_token()`
- Token expiration handling

### `backend/app/models/user.py`
- User model with UUID primary key (`id`)
- Email uniqueness validation
- `to_dict()` and `from_dict()` methods for MongoDB serialization
- Password hash storage (not plain text)

### `backend/app/models/tourist.py`
- Tourist profile model linked to User via UUID foreign key
- Profile fields: bio, phone, emergency contact, preferences

### `backend/app/models/authority.py`
- Authority profile model linked to User via UUID foreign key
- Profile fields: company name, verification status, documents

### `backend/app/schemas/user.py`
- Pydantic schemas for:
  - UserRegister: email, password, full_name, role
  - UserLogin: email, password
  - TokenRefresh: refresh_token
  - UserResponse: id, email, role, full_name
  - TouristRegister: extends UserRegister with tourist-specific fields
  - TouristProfile: tourist profile data
  - AuthorityRegister: extends UserRegister with authority-specific fields
  - AuthorityProfile: authority profile data
  - VerificationUpdate: verification status update
  - PasswordChange: password change
  - HealthCheck: health check response

### `backend/app/routers/auth.py`
- **`register`** endpoint: Creates user with hashed password, returns user data
- **`login`** endpoint: Validates credentials, returns JWT access/refresh tokens
- **`refresh`** endpoint: Refreshes access token using refresh token
- **`logout`** endpoint: Returns logout confirmation
- **`me`** endpoint: Returns current user info protected by role gating
- **`require_role`** dependency: Role-based access control

### `backend/app/routers/tourists.py`
- Tourist profile endpoints with role gating
- Only authenticated tourists can access tourist endpoints

### `backend/app/routers/authority.py`
- Authority profile endpoints with verification status
- Verification update endpoint

### `backend/tests/test_auth.py`
- Comprehensive test suite (15 test cases) for authentication flow
- Tests for registration, login, token validation, protection, logout

### `backend/.env.example`
- `MONGODB_URI`: MongoDB connection string
- `MONGODB_DATABASE`: Database name
- `JWT_SECRET_KEY`: Secret key for JWT signing
- `JWT_ALGORITHM`: Algorithm for JWT signing (HS256)
- `JWT_ACCESS_TOKEN_EXPIRES`: Access token expiration seconds
- `JWT_REFRESH_TOKEN_EXPIRES`: Refresh token expiration seconds
- `CORS_ORIGINS`: Comma-separated list of allowed CORS origins
- `EXPO_PUBLIC_API_URL`: Frontend API URL
- `EXPO_PUBLIC_WS_URL`: WebSocket URL
- `EXPO_PUBLIC_DEV_BYPASS`: Dev bypass flag
- `EXPO_PUBLIC_USE_MOCK`: Mock auth opt-in flag

## Frontend Files

### `toursafe-react/lib/api.ts`
- Axios client instance with base URL from environment
- Token refresh logic using refresh token
- 401 handling: clears auth store and redirects to login
- Request/response interceptors

### `toursafe-react/store/authStore.ts`
- JWT-based session management using AsyncStorage
- `setSession(token, user)`: Stores token and user data
- `clearSession()`: Clears auth session
- `getCurrentUser()`: Returns current user or null
- Session persistence across app restarts

### `toursafe-react/app/auth/login.tsx`
- Login form calling `/api/v1/auth/login` endpoint
- Handles authentication response
- Navigates to role selection on successful auth

### `toursafe-react/app/auth/register.tsx`
- Authority registration form calling `/api/v1/auth/register` endpoint
- Role selection after registration

### `toursafe-react/app/auth/select-role.tsx`
- Role selection screen (tourist vs authority)
- Stores selected role in auth store
- Navigates to appropriate home screen based on role

### `toursafe-react/lib/supabase.ts`
- Mock auth explicitly opt-in via `EXPO_PUBLIC_USE_MOCK` environment variable
- Production default: `EXPO_PUBLIC_USE_MOCK=false` → uses FastAPI backend
- Development: `EXPO_PUBLIC_USE_MOCK=true` → uses Supabase mock (for development only)
- This ensures mock auth is never the production default

### `toursafe-react/.env.example`
- `EXPO_PUBLIC_API_URL`: Backend API URL (e.g., http://10.0.2.2:8000)
- `EXPO_PUBLIC_WS_URL`: WebSocket URL for real-time features
- `EXPO_PUBLIC_DEV_BYPASS`: Development bypass flag
- `EXPO_PUBLIC_USE_MOCK`: Mock auth opt-in (should be false in production)

## Key Decisions

### Authentication Flow
1. Frontend sends credentials to `/api/v1/auth/login`
2. FastAPI validates against MongoDB using Argon2id password verification
3. On success, returns JWT access token + refresh token
4. Frontend stores tokens in AsyncStorage via authStore
5. API calls include `Authorization: Bearer <token>` header
6. Token refresh happens automatically on 401 responses
7. Route protection via `require_role` dependency

### Role-Based Access Control
- Role stored in user model and JWT token
- Comes from persisted data, not email inference
- `tourist` role: Can access tourist endpoints, cannot access authority endpoints
- `authority` role: Can access authority endpoints, has verification status
- Role-based endpoints: `/api/v1/authority/me` requires `authority` role

### Mock Auth Removal
- `EXPO_PUBLIC_USE_MOCK` defaults to `false` in production
- Development can set `EXPO_PUBLIC_USE_MOCK=true` for testing
- `lib/supabase.ts` checks this flag and routes accordingly
- Ensures production never depends on mock authentication

### CORS Configuration
- Origins specified via `EXPO_PUBLIC_CORS_ORIGINS` environment variable
- Dynamic configuration based on environment
- Supports both development and production origins

### Database
- MongoDB for persistence using Motor (async driver)
- User documents include: id, email, password_hash, role, full_name, is_active, timestamps
- Tourist and authority profiles linked via user ID
- Email uniqueness enforced at model level