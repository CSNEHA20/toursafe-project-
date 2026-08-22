import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status, Body
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse

from ..core.database import get_database
from ..core.input_security import sanitize_nosql_input
from ..core.rate_limiter import auth_rate_limiter, registration_rate_limiter, get_client_ip
from ..core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    revoke_token,
    validate_password_strength,
    validate_refresh_token_rotation,
)
from ..schemas.user import (
    UserRegister,
    UserLogin,
    TokenRefresh,
    UserResponse,
    TouristRegister,
    TouristProfile,
    AuthorityRegister,
    AuthorityProfile,
    VerificationUpdate,
    PasswordChange,
    HealthCheck,
)
from ..models.user import User
from ..models.tourist import Tourist
from ..models.authority import Authority
from ..services.security.security_events import security_event_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def get_current_user(token: str = Depends(oauth2_scheme)):
    """Dependency to get the current user from JWT token."""
    payload = decode_token(token)
    if payload is None or "user_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user_id = payload["user_id"]
    role = payload.get("role", "tourist")
    return user_id, role


def get_optional_current_user(token: str = Depends(optional_oauth2_scheme)):
    """Optional dependency to extract user if valid token present, else None."""
    if not token:
        return None
    payload = decode_token(token)
    if payload and "user_id" in payload:
        return payload["user_id"], payload.get("role", "tourist")
    return None


def require_role(*allowed_roles):
    """Dependency to enforce role-based access control."""

    def dependency(user_id_role: tuple = Depends(get_current_user)):
        user_id, role = user_id_role
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required one of: {', '.join(allowed_roles)}",
            )
        return user_id

    return dependency


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(request: Request, payload: dict = Body(...)):
    """Register a new user with input sanitization and rate limiting."""
    client_ip = get_client_ip(request)
    registration_rate_limiter.enforce(client_ip)

    # Sanitize NoSQL injection attempts
    clean_payload = sanitize_nosql_input(payload)

    email = clean_payload.get("email")
    password = clean_payload.get("password")
    full_name = clean_payload.get("full_name")
    role = clean_payload.get("role", "tourist")

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required.",
        )

    # Password policy check
    valid_pwd, reason = validate_password_strength(password)
    if not valid_pwd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=reason,
        )

    db = get_database()
    users = db["users"]

    existing = await users.find_one({"email": email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    password_hash = hash_password(password)
    user = User(
        email=email,
        password_hash=password_hash,
        role=role,
        full_name=full_name,
    )

    await users.insert_one(user.to_dict())

    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
    )


@router.post("/login", response_model=dict)
async def login(request: Request, payload: dict = Body(...)):
    """Login user and return JWT tokens with brute force protection."""
    client_ip = get_client_ip(request)
    auth_rate_limiter.enforce(client_ip)

    clean_payload = sanitize_nosql_input(payload)
    email = clean_payload.get("email")
    password = clean_payload.get("password")

    db = get_database()
    users = db["users"]

    user = await users.find_one({"email": email})
    if not user or not verify_password(password, user.get("password_hash", "")):
        await security_event_service.record_event(
            event_type="auth.login.failed",
            severity="MEDIUM",
            client_ip=client_ip,
            details={"email": email[:3] + "***@" if email and "@" in email else "anonymous"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
        )

    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    access_token = create_access_token(user_id=user["id"], role=user["role"], session_id=session_id)
    refresh_token = create_refresh_token(user_id=user["id"], session_id=session_id)

    # Update last_login
    user_filter = {"_id": user["_id"]} if "_id" in user else {"email": user["email"]}
    await users.update_one(
        user_filter,
        {"$set": {"last_login_at": datetime.now(timezone.utc)}},
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": UserResponse(
            id=user["id"],
            email=user["email"],
            role=user["role"],
            full_name=user.get("full_name"),
        ).model_dump(),
    }


@router.post("/refresh", response_model=dict)
async def refresh(request: Request, payload: dict = Body(...)):
    """Refresh access token using refresh token with Refresh Token Rotation (RTR)."""
    clean_payload = sanitize_nosql_input(payload)
    refresh_token = clean_payload.get("refresh_token")

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    payload_data = decode_token(refresh_token)

    if payload_data is None or "user_id" not in payload_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Validate Refresh Token Rotation & Detect Token Reuse
    is_valid_rtr, rtr_error = validate_refresh_token_rotation(payload_data)
    if not is_valid_rtr:
        client_ip = get_client_ip(request)
        await security_event_service.record_event(
            event_type="auth.token.reuse_detected",
            severity="CRITICAL",
            actor_id=payload_data.get("user_id"),
            client_ip=client_ip,
            details={"reason": rtr_error},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=rtr_error or "Token reuse detected.",
        )

    user_id = payload_data["user_id"]
    role = payload_data.get("role", "tourist")
    family_id = payload_data.get("family_id")
    session_id = payload_data.get("session_id")

    # Verify user still exists and is active
    db = get_database()
    users = db["users"]
    user = await users.find_one({"id": user_id})
    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    new_access = create_access_token(user_id=user_id, role=role, session_id=session_id)
    new_refresh = create_refresh_token(user_id=user_id, family_id=family_id, session_id=session_id)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(
    authorization: Optional[str] = Header(None),
    payload: Optional[dict] = Body(None),
):
    """Logout user and revoke active session / token."""
    # Revoke from Bearer token
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        revoke_token(token)

    # Revoke from body payload if provided
    if payload:
        if "access_token" in payload:
            revoke_token(payload["access_token"])
        if "refresh_token" in payload:
            revoke_token(payload["refresh_token"])

    return JSONResponse(content={"detail": "Logged out and tokens invalidated"}, status_code=200)


@router.get("/me")
async def me(current: tuple = Depends(get_current_user)):
    """Get current user info."""
    user_id, role = current
    db = get_database()
    users = db["users"]
    user = await users.find_one({"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {
        "id": user["id"],
        "email": user["email"],
        "role": role,
        "full_name": user.get("full_name"),
    }