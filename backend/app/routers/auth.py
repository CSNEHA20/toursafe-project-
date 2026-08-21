from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse

from ..core.database import get_database
from ..core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

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
async def register(payload: dict = Body(...)):
    """Register a new user."""
    db = get_database()
    users = db["users"]

    # Extract fields from payload
    email = payload.get("email")
    password = payload.get("password")
    full_name = payload.get("full_name")
    role = payload.get("role", "tourist")

    # Check for duplicate email
    existing = await users.find_one({"email": email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user with hashed password
    password_hash = hash_password(password)
    user = User(
        email=email,
        password_hash=password_hash,
        role=role,
        full_name=full_name,
    )

    # Insert user document directly
    await users.insert_one(user.to_dict())

    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
    )


@router.post("/login", response_model=dict)
async def login(payload: dict = Body(...)):
    """Login user and return JWT tokens."""
    db = get_database()
    users = db["users"]

    email = payload.get("email")
    password = payload.get("password")

    user = await users.find_one({"email": email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not verify_password(password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
        )

    access_token = create_access_token(user_id=user["id"], role=user["role"])
    refresh_token = create_refresh_token(user_id=user["id"])

    # Update last_login
    await users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login_at": __import__("datetime").datetime.now(__import__("timezone").utc)}},
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
async def refresh(payload: dict = Body(...)):
    """Refresh access token using refresh token."""
    refresh_token = payload.get("refresh_token")

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

    user_id = payload_data["user_id"]
    role = payload_data.get("role", "tourist")

    # Verify user still exists and is active
    db = get_database()
    users = db["users"]
    user = await users.find_one({"id": user_id})
    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    new_access = create_access_token(user_id=user_id, role=role)
    new_refresh = create_refresh_token(user_id=user_id)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout():
    """Logout user."""
    return JSONResponse(content={"detail": "Logged out"}, status_code=200)


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