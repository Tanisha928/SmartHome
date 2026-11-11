from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from app.alerts.escalation_timer import EscalationTimer


class FakeAlerts:
    def __init__(self, alert: Any) -> None:
        self.alert = alert
        self.transitions: list[tuple[Any, ...]] = []

    def list_critical_pending(self, _cutoff: datetime) -> list[Any]:
        return [self.alert]

    def transition(self, *args: Any) -> Any:
        self.transitions.append(args)
        self.alert.state = "escalated"
        return self.alert


class FakeNotifications:
    def resend_failed(self, _alert: Any) -> bool:
        return False


def test_escalation_timer_transitions_critical_alert() -> None:
    alert = SimpleNamespace(alert_id=7, state="new")
    repository = FakeAlerts(alert)
    timer = EscalationTimer(
        SimpleNamespace(),
        alert_repository=repository,
        notification_dispatcher=FakeNotifications(),
    )

    now = datetime.now(UTC)
    assert timer.run(now=now) == 1
    assert alert.state == "escalated"
    assert repository.transitions[0][1:] == ("new", "escalated", None, "auto-escalated")
