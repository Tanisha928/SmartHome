"""PrefsRepository skeleton."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.persistence.repositories.base import BaseRepository


class PrefsRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_for_user_house(self, user_id: int, house_id: int) -> list[Any]:
        raise NotImplementedError

    def upsert(self, user_id: int, house_id: int, prefs: list[dict[str, Any]]) -> list[Any]:
        raise NotImplementedError
