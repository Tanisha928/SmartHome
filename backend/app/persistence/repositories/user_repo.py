"""UserRepository skeleton."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.persistence.pg.models import User
from app.persistence.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get(self, user_id: int) -> User | None:
        raise NotImplementedError

    def get_by_email(self, email: str) -> User | None:
        raise NotImplementedError

    def create(self, **fields: Any) -> User:
        raise NotImplementedError

    def update(self, user_id: int, **fields: Any) -> User:
        raise NotImplementedError

    def house_ids_for(self, user_id: int) -> list[int]:
        raise NotImplementedError
