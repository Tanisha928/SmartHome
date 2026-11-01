"""FastAPI dependencies: claims extraction, role guards, DB session placeholder."""

from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from typing import Any, Literal

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class Claims:
    sub: int
    type: Literal["user", "device"]
    role: str | None = None
    house_ids: list[int] = field(default_factory=list)
    device_id: int | None = None
    house_id: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def user_id(self) -> int:
        return self.sub


def claims_from_payload(payload: dict[str, Any]) -> Claims:
    token_type = payload.get("type")
    if token_type not in ("user", "device"):
        raise UnauthorizedError("Invalid token type")
    try:
        sub = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise UnauthorizedError("Invalid token subject") from exc

    if token_type == "user":
        return Claims(
            sub=sub,
            type="user",
            role=str(payload.get("role", "")),
            house_ids=[int(h) for h in payload.get("house_ids", [])],
            raw=payload,
        )
    return Claims(
        sub=sub,
        type="device",
        device_id=int(payload.get("device_id", sub)),
        house_id=int(payload["house_id"]) if payload.get("house_id") is not None else None,
        raw=payload,
    )


def get_claims(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Claims:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing bearer token")
    payload = decode_token(credentials.credentials)
    claims = claims_from_payload(payload)
    request.state.claims = claims
    return claims


def require_user(claims: Claims = Depends(get_claims)) -> Claims:
    if claims.type != "user":
        raise ForbiddenError("User token required")
    return claims


def require_device(claims: Claims = Depends(get_claims)) -> Claims:
    if claims.type != "device":
        raise ForbiddenError("Device token required")
    return claims


def require_role(*roles: str) -> Callable[[Claims], Claims]:
    def _guard(claims: Claims = Depends(require_user)) -> Claims:
        if claims.role not in roles:
            raise ForbiddenError(f"Requires role: {', '.join(roles)}")
        return claims

    return _guard


def get_db() -> Generator[Any, None, None]:
    """Yield a SQLAlchemy session from persistence (imported lazily to keep core DB-free)."""
    from app.persistence.pg.session import SessionLocal

    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
