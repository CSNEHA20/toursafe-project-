import hashlib
import secrets
import uuid
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set, Tuple

from argon2 import PasswordHasher
from jose import JWTError, jwt as jose_jwt
from .config import settings

password_hasher = PasswordHasher()

# ---------------------------------------------------------------------------
# In-Memory Revocation & Refresh Family Store (with Redis fall-through)
# ---------------------------------------------------------------------------
_REVOKED_TOKENS: Set[str] = set()
_REVOKED_SESSIONS: Set[str] = set()
# Maps family_id -> { "latest_jti": str, "user_id": str, "revoked": bool }
_REFRESH_FAMILIES: Dict[str, Dict[str, Any]] = {}
# Rate limiting / failed login attempt tracker in-memory fallback
_LOGIN_ATTEMPTS: Dict[str, Dict[str, Any]] = {}


def hash_password(plain_text_password: str) -> str:
    """Hash password using Argon2id."""
    return password_hasher.hash(plain_text_password)


def verify_password(plain_text_password: str, hashed_password: str) -> bool:
    """Verify password hash safely with constant-time verification."""
    try:
        return password_hasher.verify(hashed_password, plain_text_password)
    except Exception:
        return False


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate reasonable password policy:
    - Minimum 8 characters
    - Must not be whitespace only
    """
    if not password or len(password.strip()) < 8:
        return False, "Password must be at least 8 characters in length."
    if len(password) > 256:
        return False, "Password exceeds maximum allowable length of 256 characters."
    return True, "Valid"


def create_access_token(
    user_id: str,
    role: str,
    expires_minutes: int | None = None,
    session_id: str | None = None,
    device_id: str | None = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate an RFC 7519 compliant JWT access token with unique JTI.
    """
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=expires_minutes or settings.jwt_access_expire_minutes)
    token_jti = str(uuid.uuid4())
    
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "role": role,
        "jti": token_jti,
        "token_type": "access",
        "exp": expires,
        "iat": now,
        "iss": "toursafe-auth-service",
        "aud": "toursafe-api",
    }
    if session_id:
        payload["session_id"] = session_id
    if device_id:
        payload["device_id"] = device_id
    if extra_claims:
        payload.update(extra_claims)

    return jose_jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def create_refresh_token(
    user_id: str,
    expires_days: int | None = None,
    family_id: str | None = None,
    session_id: str | None = None,
    device_id: str | None = None,
) -> str:
    """
    Generate a cryptographic refresh token with Family ID for rotation and reuse detection.
    """
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=expires_days or settings.jwt_refresh_expire_days)
    token_jti = str(uuid.uuid4())
    fam_id = family_id or str(uuid.uuid4())

    payload: Dict[str, Any] = {
        "user_id": user_id,
        "jti": token_jti,
        "family_id": fam_id,
        "token_type": "refresh",
        "exp": expires,
        "iat": now,
        "iss": "toursafe-auth-service",
        "aud": "toursafe-api",
    }
    if session_id:
        payload["session_id"] = session_id
    if device_id:
        payload["device_id"] = device_id

    # Register in refresh family tracker
    _REFRESH_FAMILIES[fam_id] = {
        "latest_jti": token_jti,
        "user_id": user_id,
        "revoked": False,
        "created_at": now.isoformat(),
    }

    return jose_jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def decode_token(token: str, verify_exp: bool = True) -> dict | None:
    """
    Decode and validate a JWT token.
    Enforces strict HS256 algorithm verification and checks revocation store.
    """
    try:
        payload = jose_jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=["HS256"],
            options={
                "verify_exp": verify_exp,
                "verify_signature": True,
                "verify_aud": False,
                "verify_iss": False,
            },
        )
        jti = payload.get("jti")
        if jti and jti in _REVOKED_TOKENS:
            return None

        session_id = payload.get("session_id")
        if session_id and session_id in _REVOKED_SESSIONS:
            return None

        return payload
    except JWTError:
        return None


def get_token_expiry(token: str) -> datetime | None:
    """Extract expiry timestamp from token."""
    try:
        payload = jose_jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=["HS256"],
            options={
                "verify_exp": False,
                "verify_signature": True,
                "verify_aud": False,
                "verify_iss": False,
            },
        )
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
    except JWTError:
        return None
    return None


def revoke_token(token_or_jti: str) -> bool:
    """
    Revoke a token by its JTI or raw token string.
    """
    if not token_or_jti:
        return False

    # If raw JWT token passed, extract JTI
    if "." in token_or_jti:
        payload = decode_token(token_or_jti, verify_exp=False)
        if payload and "jti" in payload:
            _REVOKED_TOKENS.add(payload["jti"])
            if "session_id" in payload:
                _REVOKED_SESSIONS.add(payload["session_id"])
            if "family_id" in payload:
                invalidate_refresh_family(payload["family_id"])
            return True
    
    _REVOKED_TOKENS.add(token_or_jti)
    return True


def revoke_session(session_id: str) -> bool:
    """Revoke all tokens bound to a specific session."""
    if session_id:
        _REVOKED_SESSIONS.add(session_id)
        return True
    return False


def is_token_revoked(token_or_jti: str) -> bool:
    """Check if token or JTI is in revocation store."""
    if token_or_jti in _REVOKED_TOKENS or token_or_jti in _REVOKED_SESSIONS:
        return True
    if "." in token_or_jti:
        payload = decode_token(token_or_jti, verify_exp=False)
        if not payload:
            return True
        jti = payload.get("jti")
        session_id = payload.get("session_id")
        if jti and jti in _REVOKED_TOKENS:
            return True
        if session_id and session_id in _REVOKED_SESSIONS:
            return True
    return False


def validate_refresh_token_rotation(refresh_payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validates Refresh Token Rotation (RTR).
    Detects refresh token reuse: if a refresh token is presented whose JTI does not
    match the latest known JTI for the family, the entire token family is revoked
    as an indicator of token compromise/theft.
    Returns (is_valid, error_reason).
    """
    family_id = refresh_payload.get("family_id")
    token_jti = refresh_payload.get("jti")

    # If token has no family_id (legacy token), allow single refresh
    if not family_id or not token_jti:
        return True, None

    family = _REFRESH_FAMILIES.get(family_id)
    if not family:
        # Family created or valid
        return True, None

    if family.get("revoked", False):
        return False, "Refresh token family has been revoked due to security policy."

    latest_jti = family.get("latest_jti")
    if latest_jti and latest_jti != token_jti:
        # TOKEN REUSE DETECTED!
        # Compromise event: Revoke entire token family and blacklist
        family["revoked"] = True
        _REVOKED_TOKENS.add(token_jti)
        _REVOKED_TOKENS.add(latest_jti)
        return False, "Token reuse detected. Session terminated for security."

    # Mark current JTI as consumed
    _REVOKED_TOKENS.add(token_jti)
    return True, None


def invalidate_refresh_family(family_id: str):
    """Invalidate all refresh tokens in a family."""
    if family_id in _REFRESH_FAMILIES:
        _REFRESH_FAMILIES[family_id]["revoked"] = True