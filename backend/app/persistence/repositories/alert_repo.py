"""AlertRepository — PLAN 4.4 signatures (full impl in next commit)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.deps import Claims
from app.core.errors import StateConflictError
from app.persistence.pg.models import Alert
from app.persistence.repositories.base import BaseRepository


class AlertRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def create_with_history_and_mark_event_scored(self, **kwargs: Any) -> Alert:
        raise NotImplementedError

    def transition(
        self,
        alert_id: int,
        expected: str,
        next_state: str,
        actor: int | None,
        note: str | None,
    ) -> Alert:
        raise NotImplementedError

    def append_history(
        self,
        alert_id: int,
        from_state: str | None,
        to_state: str,
        actor: int | None,
        note: str | None,
    ) -> None:
        raise NotImplementedError

    def list(self, filters: dict[str, Any], page: int, claims: Claims, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def get_detail(self, alert_id: int, claims: Claims) -> Alert:
        raise NotImplementedError

    def find_recent(self, sound_type: str, room_id: int, within_sec: int) -> Alert | None:
        raise NotImplementedError

    def increment_suppressed(self, alert_id: int) -> None:
        raise NotImplementedError

    def stats(self, **filters: Any) -> dict[str, Any]:
        raise NotImplementedError

    def raise_state_conflict(
        self, current_state: str, last_actor: int | None, changed_at: Any
    ) -> None:
        raise StateConflictError(
            "Alert state conflict",
            details={
                "current_state": current_state,
                "last_actor": last_actor,
                "changed_at": changed_at,
            },
        )
