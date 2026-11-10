"""CommandRepository — full implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.persistence.pg.models import DeviceCommand
from app.persistence.repositories.base import BaseRepository


class CommandRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def create(self, **fields: Any) -> DeviceCommand:
        pending = self.find_pending(fields["device_id"], fields["command"])
        if pending is not None:
            raise ConflictError("Command already pending", details={"error": "command_pending"})
        cmd = DeviceCommand(
            device_id=fields["device_id"],
            command=fields["command"],
            status="pending",
            issued_by=fields.get("issued_by"),
            issued_at=datetime.now(UTC),
            expires_at=fields.get("expires_at"),
        )
        self.db.add(cmd)
        self.db.flush()
        return cmd

    def pending_for_device(self, device_id: int) -> list[DeviceCommand]:
        return list(
            self.db.scalars(
                select(DeviceCommand).where(
                    DeviceCommand.device_id == device_id,
                    DeviceCommand.status == "pending",
                )
            ).all()
        )

    def find_pending(self, device_id: int, command: str) -> DeviceCommand | None:
        return self.db.scalars(
            select(DeviceCommand).where(
                DeviceCommand.device_id == device_id,
                DeviceCommand.command == command,
                DeviceCommand.status == "pending",
            )
        ).first()

    def mark_delivered(self, command_ids: list[int]) -> None:
        if not command_ids:
            return
        self.db.execute(
            update(DeviceCommand)
            .where(DeviceCommand.command_id.in_(command_ids))
            .values(status="delivered", delivered_at=datetime.now(UTC))
        )
        self.db.flush()

    def complete(self, command_id: int, result: str, *, failed: bool = False) -> DeviceCommand:
        cmd = self.db.get(DeviceCommand, command_id)
        if cmd is None:
            raise NotFoundError("Command not found")
        cmd.status = "failed" if failed else "completed"
        cmd.result = result
        cmd.completed_at = datetime.now(UTC)
        self.db.flush()
        return cmd

    def expire_stale(self, cutoff: Any) -> int:
        result = self.db.execute(
            update(DeviceCommand)
            .where(
                DeviceCommand.status == "pending",
                DeviceCommand.expires_at.is_not(None),
                DeviceCommand.expires_at < cutoff,
            )
            .values(status="expired")
        )
        self.db.flush()
        return int(result.rowcount or 0)
