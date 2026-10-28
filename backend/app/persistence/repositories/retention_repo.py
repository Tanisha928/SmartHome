"""RetentionRepository skeleton."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.persistence.pg.models import RetentionPolicy
from app.persistence.repositories.base import BaseRepository


class RetentionRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get(self) -> RetentionPolicy:
        raise NotImplementedError

    def put(self, **fields: Any) -> RetentionPolicy:
        raise NotImplementedError
