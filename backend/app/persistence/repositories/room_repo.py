"""RoomRepository skeleton."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.deps import Claims
from app.persistence.pg.models import Room
from app.persistence.repositories.base import BaseRepository


class RoomRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get(self, room_id: int, claims: Claims) -> Room:
        raise NotImplementedError

    def list(self, house_id: int | None, claims: Claims) -> list[Room]:
        raise NotImplementedError

    def create(self, **fields: Any) -> Room:
        raise NotImplementedError

    def update(self, room_id: int, **fields: Any) -> Room:
        raise NotImplementedError
