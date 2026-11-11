from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.alerts.notification_dispatcher import NotificationDispatcher
from app.alerts.recipient_resolver import RecipientResolver


def test_recipient_resolver_applies_preferences_and_default_owner_rules() -> None:
    alert = SimpleNamespace(alert_category="security", severity="high")
    owner = SimpleNamespace(user_id=1, role="owner", email="owner@example.com", phone="+15550001")
    caregiver = SimpleNamespace(
        user_id=2, role="owner", email="care@example.com", phone="+15550002"
    )
    pref = SimpleNamespace(
        user_id=2,
        alert_category="security",
        email=False,
        sms=True,
        min_severity="high",
    )

    recipients = RecipientResolver().resolve(alert, [owner, caregiver], [pref])

    assert {(r["recipient_id"], r["channel"]) for r in recipients} == {
        (1, "email"),
        (1, "sms"),
        (2, "sms"),
    }
    assert next(r for r in recipients if r["recipient_id"] == 2)["recipient_label"] == "+15550002"


class FakeNotifications:
    def __init__(self, failures: int = 0) -> None:
        self.rows: list[Any] = []
        self.failures = failures
        self.attempts = 0
        self.states: list[tuple[int, str]] = []

    def create_pending(self, _alert_id: int, recipients: list[dict[str, Any]]) -> list[Any]:
        self.rows = [
            SimpleNamespace(notification_id=i + 1, status="pending")
            for i in range(len(recipients))
        ]
        return self.rows

    def list_for_alert(self, _alert_id: int) -> list[Any]:
        return self.rows

    def mark_sent(self, notification_id: int) -> None:
        self.states.append((notification_id, "sent"))

    def mark_failed(self, notification_id: int, _error: str) -> None:
        self.states.append((notification_id, "failed"))


def test_dispatcher_retries_then_marks_sent() -> None:
    repository = FakeNotifications()
    calls = 0

    def publish(_message: dict[str, Any]) -> None:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("temporary failure")

    alert = SimpleNamespace(alert_id=3, house_id=2, severity="high", sound_type="glass_break")
    dispatcher = NotificationDispatcher(
        repository,
        publisher=publish,
        sleep=lambda _delay: None,
        retry_delays=(5, 15, 45),
    )

    assert dispatcher.dispatch(alert, [{"channel": "email"}]) is True
    assert calls == 3
    assert repository.states == [(1, "sent")]


def test_dispatcher_marks_failed_after_all_retries() -> None:
    repository = FakeNotifications()
    dispatcher = NotificationDispatcher(
        repository,
        publisher=lambda _message: (_ for _ in ()).throw(RuntimeError("down")),
        sleep=lambda _delay: None,
        retry_delays=(5, 15, 45),
    )
    alert = SimpleNamespace(alert_id=3, house_id=2, severity="high", sound_type="glass_break")

    assert dispatcher.dispatch(alert, [{"channel": "email"}]) is False
    assert repository.states == [(1, "failed")]
