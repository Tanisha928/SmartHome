"""NotificationRepository skeleton."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.persistence.repositories.base import BaseRepository


class NotificationRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def create_pending(self, alert_id: int, recipients: list[dict[str, Any]]) -> list[Any]:
        raise NotImplementedError

    def mark_sent(self, notification_id: int) -> None:
        raise NotImplementedError

    def mark_failed(self, notification_id: int, error: str) -> None:
        raise NotImplementedError

    def list_for_alert(self, alert_id: int) -> list[Any]:
        raise NotImplementedError
