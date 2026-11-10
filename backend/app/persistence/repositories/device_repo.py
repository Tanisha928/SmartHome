"""DeviceRepository — full implementation."""

from __future__ import annotations

import builtins
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.deps import Claims
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.persistence.pg.models import Device
from app.persistence.repositories.base import BaseRepository


def _page(page: int, page_size: int) -> tuple[int, int]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    return page, page_size


class DeviceRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get(self, device_id: int, claims: Claims) -> Device:
        stmt = select(Device).where(Device.device_id == device_id, Device.removed_at.is_(None))
        stmt = self.apply_scope(
            stmt, claims, Device.house_id, action="get_device", resource=f"device:{device_id}"
        )
        device = self.db.scalars(stmt).first()
        if device is None:
            existing = self.db.get(Device, device_id)
            if existing is None or existing.removed_at is not None:
                raise NotFoundError("Device not found")
            raise ForbiddenError("Device out of scope")
        return device

    def get_raw(self, device_id: int) -> Device | None:
        return self.db.get(Device, device_id)

    def list(
        self,
        filters: dict[str, Any],
        page: int,
        claims: Claims,
        *,
        page_size: int = 25,
    ) -> dict[str, Any]:
        page, page_size = _page(page, page_size)
        stmt = select(Device).where(Device.removed_at.is_(None))
        if filters.get("house_id") is not None:
            stmt = stmt.where(Device.house_id == filters["house_id"])
        if filters.get("room_id") is not None:
            stmt = stmt.where(Device.room_id == filters["room_id"])
        if filters.get("status") is not None:
            stmt = stmt.where(Device.status == filters["status"])
        if filters.get("connectivity") is not None:
            stmt = stmt.where(Device.conn_state == filters["connectivity"])
        stmt = self.apply_scope(stmt, claims, Device.house_id, action="list_devices", resource="devices")
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            self.db.scalars(
                stmt.order_by(Device.device_id).offset((page - 1) * page_size).limit(page_size)
            ).all()
        )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def create(self, **fields: Any) -> Device:
        if self.find_by_serial(fields["serial_no"]):
            raise ConflictError("Serial already registered", details={"error": "duplicate_serial"})
        device = Device(
            room_id=fields["room_id"],
            house_id=fields["house_id"],
            device_type=fields["device_type"],
            serial_no=fields["serial_no"],
            label=fields.get("label"),
            status=fields.get("status", "enabled"),
            conn_state=fields.get("conn_state", "offline"),
            threshold=fields.get("threshold"),
            api_key_hash=fields["api_key_hash"],
            api_key_prefix=fields.get("api_key_prefix"),
        )
        self.db.add(device)
        self.db.flush()
        return device

    def update(self, device_id: int, **fields: Any) -> Device:
        device = self.get_raw(device_id)
        if device is None or device.removed_at is not None:
            raise NotFoundError("Device not found")
        for key, value in fields.items():
            if hasattr(device, key) and value is not None:
                setattr(device, key, value)
        self.db.flush()
        return device

    def find_by_serial(self, serial_no: str) -> Device | None:
        return self.db.scalars(
            select(Device).where(Device.serial_no == serial_no, Device.removed_at.is_(None))
        ).first()

    def mark_offline_stale(self, cutoff: datetime) -> int:
        result = self.db.execute(
            update(Device)
            .where(
                Device.status == "enabled",
                Device.conn_state == "online",
                Device.last_heartbeat.is_not(None),
                Device.last_heartbeat < cutoff,
                Device.removed_at.is_(None),
            )
            .values(conn_state="offline")
        )
        self.db.flush()
        return int(result.rowcount or 0)

    def stale_online_ids(self, cutoff: datetime) -> builtins.list[int]:
        """IDs of enabled, online devices whose last heartbeat is older than cutoff."""
        return list(
            self.db.scalars(
                select(Device.device_id).where(
                    Device.status == "enabled",
                    Device.conn_state == "online",
                    Device.last_heartbeat.is_not(None),
                    Device.last_heartbeat < cutoff,
                    Device.removed_at.is_(None),
                )
            ).all()
        )

    def list_for_house(self, house_id: int) -> builtins.list[Device]:
        """All non-removed devices in a house (unscoped; caller must authorize)."""
        return list(
            self.db.scalars(
                select(Device)
                .where(Device.house_id == house_id, Device.removed_at.is_(None))
                .order_by(Device.device_id)
            ).all()
        )

    def soft_remove(self, device_id: int) -> Device:
        now = datetime.now(UTC)
        return self.update(device_id, removed_at=now, key_revoked_at=now)
