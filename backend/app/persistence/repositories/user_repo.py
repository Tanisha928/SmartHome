"""UserRepository — full implementation."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.persistence.pg.models import User, UserHouse
from app.persistence.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalars(select(User).where(User.email == email.lower())).first()

    def create(self, **fields: Any) -> User:
        email = str(fields["email"]).lower()
        if self.get_by_email(email):
            raise ConflictError("Email already registered", details={"error": "duplicate_email"})
        user = User(
            email=email,
            password_hash=fields["password_hash"],
            full_name=fields.get("full_name"),
            phone=fields.get("phone"),
            role=fields.get("role", "owner"),
            must_reset=bool(fields.get("must_reset", False)),
        )
        self.db.add(user)
        self.db.flush()
        return user

    def update(self, user_id: int, **fields: Any) -> User:
        user = self.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        for key in ("full_name", "phone", "email", "password_hash", "must_reset"):
            if key in fields and fields[key] is not None:
                setattr(user, key, fields[key] if key != "email" else str(fields[key]).lower())
        self.db.flush()
        return user

    def house_ids_for(self, user_id: int) -> list[int]:
        rows = self.db.scalars(select(UserHouse.house_id).where(UserHouse.user_id == user_id)).all()
        return list(rows)
