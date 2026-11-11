"""Auth service — signup, login, refresh, logout, profile, saved-views."""

from __future__ import annotations

from typing import Any

from app.core.deps import Claims
from app.core.errors import UnauthorizedError
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.persistence.pg.models import User
from app.persistence.repositories.saved_views_repo import SavedViewsRepository
from app.persistence.repositories.dashboard_settings_repo import DashboardSettingsRepository
from app.persistence.repositories.user_repo import UserRepository


class AuthService:
    def __init__(self, db: Any) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.saved_views = SavedViewsRepository(db)
        self.dashboard_settings = DashboardSettingsRepository(db)

    def signup(self, email: str, password: str, full_name: str, phone: str | None) -> User:
        return self.users.create(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            phone=phone,
            role="owner",
        )

    def login(self, email: str, password: str) -> tuple[str, int, str, User, list[int]]:
        user = self.users.get_by_email(email)
        if user is None:
            verify_password(password, DUMMY_PASSWORD_HASH)
            raise UnauthorizedError("Invalid credentials")
        if not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid credentials")
        house_ids = self.users.house_ids_for(user.user_id)
        access, expires_in = create_access_token(
            subject=user.user_id, role=user.role, house_ids=house_ids
        )
        refresh = create_refresh_token(subject=user.user_id)
        return access, expires_in, refresh, user, house_ids

    def refresh(self, refresh_token: str) -> tuple[str, int, str, User, list[int]]:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid refresh token")
        user = self.users.get(int(payload["sub"]))
        if user is None:
            raise UnauthorizedError("Invalid refresh token")
        house_ids = self.users.house_ids_for(user.user_id)
        access, expires_in = create_access_token(
            subject=user.user_id, role=user.role, house_ids=house_ids
        )
        new_refresh = create_refresh_token(subject=user.user_id)
        return access, expires_in, new_refresh, user, house_ids

    def me(self, claims: Claims) -> tuple[User, list[int]]:
        user = self.users.get(claims.user_id)
        if user is None:
            raise UnauthorizedError("User not found")
        return user, self.users.house_ids_for(user.user_id)

    def update_me(self, claims: Claims, **fields: Any) -> tuple[User, list[int]]:
        user = self.users.update(claims.user_id, **fields)
        return user, self.users.house_ids_for(user.user_id)

    def get_saved_views(self, user_id: int) -> list[dict[str, Any]]:
        return self.saved_views.get_for_user(user_id)

    def put_saved_views(self, user_id: int, views: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.saved_views.replace_for_user(user_id, views)

    def get_dashboard_settings(self, user_id: int) -> dict[str, Any]:
        return self.dashboard_settings.payload(self.dashboard_settings.get_or_create(user_id))

    def put_dashboard_settings(self, user_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        return self.dashboard_settings.payload(self.dashboard_settings.update(user_id, **fields))


def user_payload(user: User, house_ids: list[int]) -> dict[str, Any]:
    return {
        "id": user.user_id,
        "name": user.full_name,
        "email": user.email,
        "role": user.role,
        "house_ids": house_ids,
        "phone": user.phone,
        "must_reset": user.must_reset,
    }
