"""NotificationRepository — full implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.pg.models import AlertNotification
from app.persistence.repositories.base import BaseRepository


class NotificationRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def create_pending(
        self, alert_id: int, recipients: list[dict[str, Any]]
    ) -> list[AlertNotification]:
        rows: list[AlertNotification] = []
        for r in recipients:
            row = AlertNotification(
                alert_id=alert_id,
                recipient_id=r.get("recipient_id"),
                recipient_label=r.get("recipient_label"),
                channel=r["channel"],
                status="pending",
                attempts=0,
            )
            self.db.add(row)
            rows.append(row)
        self.db.flush()
        return rows

    def mark_sent(self, notification_id: int) -> None:
        row = self.db.get(AlertNotification, notification_id)
        if row:
            row.status = "sent"
            row.sent_at = datetime.now(UTC)
            row.attempts = int(row.attempts or 0) + 1
            self.db.flush()

    def mark_failed(self, notification_id: int, error: str) -> None:
        row = self.db.get(AlertNotification, notification_id)
        if row:
            row.status = "failed"
            row.last_error = error
            row.attempts = int(row.attempts or 0) + 1
            self.db.flush()

    def list_for_alert(self, alert_id: int) -> list[AlertNotification]:
        return list(
            self.db.scalars(
                select(AlertNotification).where(AlertNotification.alert_id == alert_id)
            ).all()
        )
