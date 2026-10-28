"""DeviceRepository — PLAN 4.4 signatures."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.deps import Claims
from app.persistence.pg.models import Device
from app.persistence.repositories.base import BaseRepository


class DeviceRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get(self, device_id: int, claims: Claims) -> Device:
        raise NotImplementedError

    def list(
        self,
        filters: dict[str, Any],
        page: int,
        claims: Claims,
        *,
        page_size: int = 25,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def create(self, **fields: Any) -> Device:
        raise NotImplementedError

    def update(self, device_id: int, **fields: Any) -> Device:
        raise NotImplementedError

    def find_by_serial(self, serial_no: str) -> Device | None:
        raise NotImplementedError

    def mark_offline_stale(self, cutoff: datetime) -> int:
        raise NotImplementedError
