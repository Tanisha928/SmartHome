"""Automatic escalation for critical alerts left unattended."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.alerts.alert_state_service import AlertStateService
from app.alerts.events import publish_alert
from app.alerts.notification_dispatcher import NotificationDispatcher
from app.core.config import get_settings
from app.persistence.repositories.alert_repo import AlertRepository
from app.persistence.repositories.notification_repo import NotificationRepository


class EscalationTimer:
    def __init__(
        self,
        db: Any,
        *,
        alert_repository: Any | None = None,
        notification_dispatcher: Any | None = None,
    ) -> None:
        self.db = db
        self.alerts = alert_repository or AlertRepository(db)
        self.notifications = notification_dispatcher or NotificationDispatcher(
            NotificationRepository(db)
        )

    def run(self, now: datetime | None = None) -> int:
        current = now or datetime.now(UTC)
        cutoff = current - timedelta(minutes=get_settings().escalate_after_min)
        count = 0
        for alert in self.alerts.list_critical_pending(cutoff):
            updated = AlertStateService(self.alerts).transition(
                int(alert.alert_id),
                current_state=alert.state,
                next_state="escalated",
                role="admin",
                actor=None,
                note="auto-escalated",
            )
            self.notifications.resend_failed(updated)
            publish_alert(self.db, "alert.updated", updated)
            count += 1
        return count
