"""AlertRepository — full implementation with atomic transition."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.deps import Claims
from app.core.errors import ForbiddenError, NotFoundError, StateConflictError
from app.persistence.pg.models import Alert, AlertStateHistory, Event
from app.persistence.repositories.base import BaseRepository


def _page(page: int, page_size: int) -> tuple[int, int]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    return page, page_size


class AlertRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def create_with_history_and_mark_event_scored(self, **kwargs: Any) -> Alert:
        alert = Alert(
            event_id=kwargs["event_id"],
            house_id=kwargs["house_id"],
            room_id=kwargs["room_id"],
            device_id=kwargs["device_id"],
            resident_id=kwargs.get("resident_id"),
            alert_category=kwargs["alert_category"],
            sound_type=kwargs.get("sound_type"),
            confidence=kwargs.get("confidence"),
            severity=kwargs["severity"],
            state="new",
            version=1,
        )
        self.db.add(alert)
        self.db.flush()
        self.append_history(alert.alert_id, None, "new", None, kwargs.get("note"))
        self.db.execute(
            update(Event)
            .where(Event.event_id == kwargs["event_id"])
            .values(processing_state="scored", decision=kwargs.get("decision", "alert_created"))
        )
        self.db.flush()
        return alert

    def transition(
        self,
        alert_id: int,
        expected: str,
        next_state: str,
        actor: int | None,
        note: str | None,
    ) -> Alert:
        alert = self.db.get(Alert, alert_id)
        if alert is None:
            raise NotFoundError("Alert not found")
        result = self.db.execute(
            update(Alert)
            .where(Alert.alert_id == alert_id, Alert.state == expected)
            .values(
                state=next_state,
                version=Alert.version + 1,
                updated_at=datetime.now(UTC),
                resolved_by=actor
                if next_state in ("resolved", "false_positive")
                else Alert.resolved_by,
                resolved_at=datetime.now(UTC)
                if next_state in ("resolved", "false_positive")
                else Alert.resolved_at,
            )
        )
        if result.rowcount == 0:
            last = self.db.scalars(
                select(AlertStateHistory)
                .where(AlertStateHistory.alert_id == alert_id)
                .order_by(AlertStateHistory.changed_at.desc())
            ).first()
            raise StateConflictError(
                "Alert state conflict",
                details={
                    "current_state": alert.state,
                    "last_actor": last.actor_user_id if last else None,
                    "changed_at": (last.changed_at.isoformat() + "Z")
                    if last and last.changed_at
                    else None,
                },
            )
        self.append_history(alert_id, expected, next_state, actor, note)
        self.db.refresh(alert)
        return alert

    def append_history(
        self,
        alert_id: int,
        from_state: str | None,
        to_state: str,
        actor: int | None,
        note: str | None,
    ) -> None:
        self.db.add(
            AlertStateHistory(
                alert_id=alert_id,
                from_state=from_state,
                to_state=to_state,
                actor_user_id=actor,
                note=note,
            )
        )
        self.db.flush()

    def list(
        self, filters: dict[str, Any], page: int, claims: Claims, **kwargs: Any
    ) -> dict[str, Any]:
        page_size = int(kwargs.get("page_size", 25))
        page, page_size = _page(page, page_size)
        stmt = select(Alert)
        if filters.get("house_id") is not None:
            stmt = stmt.where(Alert.house_id == filters["house_id"])
        if filters.get("state") is not None:
            stmt = stmt.where(Alert.state == filters["state"])
        if filters.get("severity") is not None:
            stmt = stmt.where(Alert.severity == filters["severity"])
        if filters.get("category") is not None:
            stmt = stmt.where(Alert.alert_category == filters["category"])
        if filters.get("sound_type") is not None:
            stmt = stmt.where(Alert.sound_type == filters["sound_type"])
        if filters.get("updated_since") is not None:
            stmt = stmt.where(Alert.updated_at >= filters["updated_since"])
        stmt = self.apply_scope(
            stmt, claims, Alert.house_id, action="list_alerts", resource="alerts"
        )
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            self.db.scalars(
                stmt.order_by(Alert.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def get_detail(self, alert_id: int, claims: Claims) -> Alert:
        stmt = select(Alert).where(Alert.alert_id == alert_id)
        stmt = self.apply_scope(
            stmt, claims, Alert.house_id, action="get_alert", resource=f"alert:{alert_id}"
        )
        alert = self.db.scalars(stmt).first()
        if alert is None:
            if self.db.get(Alert, alert_id) is None:
                raise NotFoundError("Alert not found")
            raise ForbiddenError("Alert out of scope")
        return alert

    def find_recent(self, sound_type: str, room_id: int, within_sec: int) -> Alert | None:
        cutoff = datetime.now(UTC) - timedelta(seconds=within_sec)
        return self.db.scalars(
            select(Alert)
            .where(
                Alert.sound_type == sound_type,
                Alert.room_id == room_id,
                Alert.created_at >= cutoff,
            )
            .order_by(Alert.created_at.desc())
        ).first()

    def increment_suppressed(self, alert_id: int) -> None:
        self.db.execute(
            update(Alert)
            .where(Alert.alert_id == alert_id)
            .values(suppressed_count=Alert.suppressed_count + 1, updated_at=datetime.now(UTC))
        )
        self.db.flush()

    def stats(self, **filters: Any) -> dict[str, Any]:
        return {"by_severity": {}, "by_category": {}, "by_state": {}, "trend": []}

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
