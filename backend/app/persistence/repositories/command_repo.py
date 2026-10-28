"""CommandRepository skeleton."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.persistence.pg.models import DeviceCommand
from app.persistence.repositories.base import BaseRepository


class CommandRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def create(self, **fields: Any) -> DeviceCommand:
        raise NotImplementedError

    def pending_for_device(self, device_id: int) -> list[DeviceCommand]:
        raise NotImplementedError

    def find_pending(self, device_id: int, command: str) -> DeviceCommand | None:
        raise NotImplementedError

    def mark_delivered(self, command_ids: list[int]) -> None:
        raise NotImplementedError

    def complete(self, command_id: int, result: str, *, failed: bool = False) -> DeviceCommand:
        raise NotImplementedError

    def expire_stale(self, cutoff: Any) -> int:
        raise NotImplementedError
