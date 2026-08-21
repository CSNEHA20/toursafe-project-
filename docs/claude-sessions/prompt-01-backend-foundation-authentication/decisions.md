# Decisions: Backend Foundation Authentication

## Architectural Decisions

### 1. FastAPI + MongoDB Stack
- **Decision**: Use FastAPI with Motor (async MongoDB driver) instead of Flask or SQLAlchemy
- **Rationale**: 
  - FastAPI provides automatic OpenAPI docs, type validation, and modern Python features
  - Motor is the async driver for MongoDB, suitable for Expo's async architecture
  - Better performance than synchronous drivers for I/O-bound operations
- **Alternative considered**: Flask-SQLAlchemy, but rejected for lack of async support and modern auth patterns

### 2. Argon2id Password Hashing
- **Decision**: Use Argon2id for all password hashing
- **Rationale**: 
  - Argon2id is the recommended password hashing algorithm (winner of Password Hashing Competition 2015)
  - Provides resistance against GPU cracking attacks
  - More secure than bcrypt or PBKDF2 for new implementations
- **Implementation**: `app/core/security.py` with `hash_password()` and `verify_password()` functions

### 3. JWT Token-Based Authentication
- **Decision**: Use JSON Web Tokens (JWT) for stateless authentication
- **Rationale**: 
  - Stateless: No server-side session storage needed
  - Self-contained: Contains user ID and role in payload
  - Standard: Widely supported across platforms (React Native, web, etc.)
  - Token refresh: Access tokens short-lived, refresh tokens for renewal
- **Implementation**:
  - Access tokens: 15-minute expiry
  - Refresh tokens: 7-day expiry
  - Signed with HS256 using `JWT_SECRET_KEY` from environment

### 4. Role-Based Access Control (RBAC)
- **Decision**: Role-based access control with roles stored in persisted data
- **Rationale**: 
  - Role comes from database, not email inference
  - Clear separation between tourist and authority capabilities
  - Easy to extend with additional roles later
- **Implementation**:
  - Role stored in User model and JWT token payload
  - `require_role()` dependency in routers enforces access
  - Tourist cannot access authority endpoints and vice versa

### 5. Mock Auth Opt-In via Environment Variable
- **Decision**: `EXPO_PUBLIC_USE_MOCK` must be explicitly set to `true` for mock auth
- **Rationale**: 
  - Production default: FastAPI backend (real authentication)
  - Development can use mock for testing without affecting production
  - Prevents accidentally shipping mock auth to production
- **Implementation**:
  - `toursafe-react/lib/supabase.ts` checks `EXPO_PUBLIC_USE_MOCK`
  - When `false` (default): uses FastAPI backend endpoints
  - When `true`: uses Supabase mock authentication
  - Environment variable format: `EXPO_PUBLIC_USE_MOCK=false`

### 6. Development Bypass Flag
- **Decision**: `EXPO_PUBLIC_DEV_BYPASS` exists but real auth is default
- **Rationale**: 
  - Allows development shortcuts when needed
  - Cannot be used to bypass production security requirements
  - Clear separation between dev and prod paths
- **Implementation**:
  - `EXPO_PUBLIC_DEV_BYPASS` environment variable
  - Controlled feature flag, not a security bypass

### 7. Router Prefix Fix
- **Decision**: Remove duplicate `/api/v1` prefix from router inclusion in `main.py`
- **Rationale**: 
  - Original: `app.include_router(auth_router, prefix="/api/v1")` 
  - Routers already had `/api/v1/` in their path definitions
  - Resulted in `/api/v1/api/v1/auth/register` - double prefix
  - Fixed by changing to `app.include_router(auth_router)` (routers define their own paths)
- **Impact**: All endpoint URLs now correctly formatted as `/api/v1/auth/...`

### 8. CORS Configuration from Environment
- **Decision**: CORS origins configured via `EXPO_PUBLIC_CORS_ORIGINS` env var
- **Rationale**: 
  - Different origins for development (localhost) vs production (deployed URL)
  - Dynamic configuration without code changes
  - Secure by default - no wildcard origins
- **Implementation**:
  - `app/core/config.py` parses comma-separated origins
  - Falls back to empty list if not configured
  - `app/main.py` uses `settings.cors_origins` for middleware configuration

### 9. Frontend Auth Store with AsyncStorage
- **Decision**: Use React Native AsyncStore for JWT token persistence
- **Rationale**: 
  - Persists across app restarts
  - Secure storage of sensitive tokens
  - Works with React Native's async architecture
  - Enables token refresh without re-login
- **Implementation**:
  - `toursafe-react/store/authStore.ts` manages token lifecycle
  - `api.ts` handles token refresh on 401 responses
  - Automatic logout when tokens expire

### 10. Supabase Mock Isolated, Production Disabled
- **Decision**: Mock auth via Supabase is opt-in only via `EXPO_PUBLIC_USE_MOCK`
- **Rationale**: 
  - Prevents production dependency on mock authentication
  - Clear separation between dev and prod environments
  - Easy to disable mock when moving to production
- **Implementation**:
  - `toursafe-react/lib/supabase.ts` checks environment flag
  - Default `EXPO_PUBLIC_USE_MOCK=false` routes to FastAPI
  - `EXPO_PUBLIC_USE_MOCK=true` enables mock for development/testing only

## Code Organization Decisions

### Modular App Layout
- `app/main.py` - FastAPI entry point, CORS, router inclusion
- `app/core/config.py` - Settings and environment configuration
- `app/core/database.py` - MongoDB connection management
- `app/core/security.py` - Authentication and password hashing
- `app/models/` - Database models (user, tourist, authority)
- `app/schemas/` - Pydantic validation schemas
- `app/routers/` - API endpoint routers (auth, tourists, authority)

### Separation of Concerns
- Models: Data structure and MongoDB operations
- Schemas: Pydantic validation and serialization
- Routers: HTTP endpoints and dependency injection
- Core: Shared utilities (config, database, security)
- Frontend: React Native components and state management

### Environment Configuration
- All sensitive values via environment variables (`.env.example`)
- No hardcoded secrets or credentials
- `.env.example` provides defaults and documentation
- Production uses different values than development

## Security Decisions

### Password Security
- Argon2id hashing with recommended parameters
- Never store plaintext passwords
- Password verification constant-time comparison

### JWT Security
- Secret key from environment variable (never hardcoded)
- Short-lived access tokens (15 minutes)
- Refresh tokens with longer expiry (7 days)
- Token payload contains only: user_id, role (no sensitive data)

### Role Validation
- Role comes from persisted user model, not client-supplied data
- Server enforces role-based access control
- Cannot be inferred from email domain or username

### CORS Security
- No wildcard (`*`) origins
- Explicit origins list from environment
- Credentials enabled (`allow_credentials=True`)

### Data Isolation
- User IDs are UUIDs (not sequential or predictable)
- Tourist and authority profiles linked via user ID foreign key
- Email uniqueness enforced at model level