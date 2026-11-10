"""Auth and profile request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10)
    full_name: str
    phone: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    expires_in: int
    user: dict[str, Any]


class UserProfile(BaseModel):
    id: int
    email: str
    name: str | None
    phone: str | None
    role: str
    house_ids: list[int]
    must_reset: bool = False


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None


class SavedViewsPayload(BaseModel):
    views: list[dict[str, Any]] = Field(default_factory=list)
