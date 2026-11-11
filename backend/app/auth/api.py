"""Auth HTTP endpoints — PLAN section 5.2."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from app.auth.schemas import (
    LoginRequest,
    SavedViewsPayload,
    DashboardSettingsPayload,
    SignupRequest,
    TokenResponse,
    UpdateProfileRequest,
)
from app.auth.service import AuthService, user_payload
from app.core.config import get_settings
from app.core.deps import Claims, get_db, require_user
from app.core.errors import UnauthorizedError
from app.core.ratelimit import login_limiter

router = APIRouter(tags=["auth"])

REFRESH_COOKIE = "rt"
COOKIE_MAX_AGE = 7 * 24 * 60 * 60


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.env not in ("dev", "test"),
        samesite="strict",
        max_age=COOKIE_MAX_AGE,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path="/api/auth")


@router.post("/api/auth/signup", status_code=201)
def signup(body: SignupRequest, db: Any = Depends(get_db)) -> dict[str, Any]:
    service = AuthService(db)
    user = service.signup(body.email, body.password, body.full_name, body.phone)
    return {"id": user.user_id, "email": user.email, "role": user.role}


@router.post("/api/auth/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Any = Depends(get_db),
) -> TokenResponse:
    key = f"{request.client.host if request.client else 'unknown'}:{body.email.lower()}"
    login_limiter.check(key)
    service = AuthService(db)
    access, expires_in, refresh, user, house_ids = service.login(body.email, body.password)
    login_limiter.reset(key)
    _set_refresh_cookie(response, refresh)
    return TokenResponse(
        access_token=access,
        expires_in=expires_in,
        user=user_payload(user, house_ids),
    )


@router.post("/api/auth/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Any = Depends(get_db)) -> TokenResponse:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise UnauthorizedError("Missing refresh cookie")
    service = AuthService(db)
    access, expires_in, new_refresh, user, house_ids = service.refresh(token)
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(
        access_token=access,
        expires_in=expires_in,
        user=user_payload(user, house_ids),
    )


@router.post("/api/auth/logout", status_code=204)
def logout(response: Response) -> Response:
    _clear_refresh_cookie(response)
    response.status_code = 204
    return response


@router.get("/api/users/me")
def get_me(claims: Claims = Depends(require_user), db: Any = Depends(get_db)) -> dict[str, Any]:
    user, house_ids = AuthService(db).me(claims)
    return user_payload(user, house_ids)


@router.put("/api/users/me")
def put_me(
    body: UpdateProfileRequest,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    fields = body.model_dump(exclude_unset=True)
    user, house_ids = AuthService(db).update_me(claims, **fields)
    return user_payload(user, house_ids)


@router.get("/api/users/me/saved-views")
def get_saved_views(
    claims: Claims = Depends(require_user), db: Any = Depends(get_db)
) -> dict[str, Any]:
    return {"views": AuthService(db).get_saved_views(claims.user_id)}


@router.put("/api/users/me/saved-views")
def put_saved_views(
    body: SavedViewsPayload,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    views = AuthService(db).put_saved_views(claims.user_id, body.views)
    return {"views": views}


@router.get("/api/users/me/dashboard-settings")
def get_dashboard_settings(claims: Claims = Depends(require_user), db: Any = Depends(get_db)) -> dict[str, Any]:
    return AuthService(db).get_dashboard_settings(claims.user_id)


@router.put("/api/users/me/dashboard-settings")
def put_dashboard_settings(
    body: DashboardSettingsPayload,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    return AuthService(db).put_dashboard_settings(claims.user_id, body.model_dump())
