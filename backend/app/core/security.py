"""JWT encode/decode, password hashing, and API-key hashing."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.errors import UnauthorizedError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Constant-time dummy hash for unknown-email login (bcrypt of "dummy-password-never-used")
DUMMY_PASSWORD_HASH = pwd_context.hash("dummy-password-never-used")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_device_api_key() -> tuple[str, str, str]:
    """Return (raw_key, sha256_hash, prefix). Raw key shown once."""
    raw = f"dk_{secrets.token_urlsafe(32)}"
    return raw, hash_api_key(raw), raw[:10]


TokenType = Literal["user", "device", "refresh"]


def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(
    *,
    subject: int,
    role: str,
    house_ids: list[int],
    extra: dict[str, Any] | None = None,
) -> tuple[str, int]:
    settings = get_settings()
    expires_in = settings.access_token_min * 60
    now = _now()
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "user",
        "role": role,
        "house_ids": house_ids,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)
    return token, expires_in


def create_device_token(*, device_id: int, house_id: int) -> tuple[str, int]:
    settings = get_settings()
    expires_in = settings.device_token_min * 60
    now = _now()
    payload = {
        "sub": str(device_id),
        "type": "device",
        "device_id": device_id,
        "house_id": house_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)
    return token, expires_in


def create_refresh_token(*, subject: int) -> str:
    settings = get_settings()
    now = _now()
    payload = {
        "sub": str(subject),
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.refresh_token_days)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except JWTError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc
