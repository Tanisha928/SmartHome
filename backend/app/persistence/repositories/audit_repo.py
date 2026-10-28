"""AuditRepository skeleton."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.persistence.repositories.base import BaseRepository


class AuditRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def log_admin_read(self, **fields: Any) -> None:
        raise NotImplementedError

    def query(
        self,
        house: int | None,
        actor: int | None,
        type_: str | None,
        range_: Any,
        page: int,
        *,
        page_size: int = 25,
    ) -> dict[str, Any]:
        raise NotImplementedError
