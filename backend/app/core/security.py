import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from jose import JWTError, jwt as jwt_encode
from .config import settings

password_hasher = PasswordHasher()


def hash_password(plain_text_password: str) -> str:
    return password_hasher.hash(plain_text_password)


def verify_password(plain_text_password: str, hashed_password: str) -> bool:
    try:
        return password_hasher.verify(hashed_password, plain_text_password)
    except Exception:
        return False


def create_access_token(user_id: str, role: str, expires_minutes: int | None = None) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or 30)
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": expires,
        "iat": datetime.now(timezone.utc),
    }
    encoded = jwt_encode.encode(payload, settings.jwt_secret_key, algorithm="HS256")
    return encoded


def create_refresh_token(user_id: str, expires_days: int | None = None) -> str:
    expires = datetime.now(timezone.utc) + timedelta(days=expires_days or 7)
    payload = {
        "user_id": user_id,
        "exp": expires,
        "iat": datetime.now(timezone.utc),
    }
    encoded = jwt_encode.encode(payload, settings.jwt_secret_key, algorithm="HS256")
    return encoded


def decode_token(token: str) -> dict | None:
    try:
        payload = jwt_encode.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


def get_token_expiry(token: str) -> datetime | None:
    try:
        payload = jwt_encode.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
    except JWTError:
        return None