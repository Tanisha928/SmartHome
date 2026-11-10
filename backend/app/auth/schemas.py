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
    # Plain str: login only looks the address up. EmailStr rejects reserved domains such as
    # the seeded *@smarthome.local accounts, which would make them impossible to sign in.
    email: str = Field(min_length=3, max_length=320)
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
