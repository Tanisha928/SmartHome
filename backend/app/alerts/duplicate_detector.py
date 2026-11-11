"""Duplicate-alert detection boundary."""

from __future__ import annotations

from typing import Any, Protocol


class RecentAlertRepository(Protocol):
    def find_recent(self, sound_type: str, room_id: int, within_sec: int) -> Any | None: ...

    def increment_suppressed(self, alert_id: int) -> None: ...


class DuplicateDetector:
    def __init__(self, repository: RecentAlertRepository, window_seconds: int = 60) -> None:
        self.repository = repository
        self.window_seconds = window_seconds

    def find_recent(self, sound_type: str, room_id: int) -> Any | None:
        return self.repository.find_recent(sound_type, room_id, self.window_seconds)

    def suppress(self, alert: Any) -> None:
        self.repository.increment_suppressed(alert.alert_id)
