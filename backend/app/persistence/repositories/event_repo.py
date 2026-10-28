"""EventRepository — PLAN 4.4 signatures."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.persistence.pg.models import Event
from app.persistence.repositories.base import BaseRepository


class EventRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def create_if_new(
        self,
        device_id: int,
        captured_at: datetime,
        s3_key: str,
        house_id: int,
        duration: float | None,
        correlation_id: str,
        *,
        event_id: int | None = None,
    ) -> tuple[Event, bool]:
        raise NotImplementedError

    def find(self, device_id: int, captured_at: datetime) -> Event | None:
        raise NotImplementedError

    def get(self, event_id: int) -> Event | None:
        raise NotImplementedError

    def list_admin(
        self,
        state: str | None,
        house: int | None,
        age: Any,
        page: int,
        *,
        page_size: int = 25,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def mark_scored(self, event_id: int, decision: str) -> None:
        raise NotImplementedError

    def list_stale_queued(self, older_than: datetime) -> list[Event]:
        raise NotImplementedError

    def increment_retry(self, event_id: int) -> Event:
        raise NotImplementedError

    def set_failed(self, event_id: int) -> Event:
        raise NotImplementedError
