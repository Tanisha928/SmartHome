"""CommandQueue — issue, deliver, ack, expire device commands (PLAN 6.1/6.2, S6)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.iot.errors import CommandPendingError
from app.iot.timeutil import utcnow
from app.persistence.repositories.command_repo import CommandRepository

COMMANDS = ("enable", "disable", "reboot")


class CommandQueue:
    def __init__(self, db: Any) -> None:
        self.commands = CommandRepository(db)
        self.settings = get_settings()

    def issue(self, device_id: int, command: str, issued_by: int | None) -> Any:
        """Create a pending command; 409 `command_pending` if the same one is already queued."""
        self.expire_stale()
        expires_at = utcnow() + timedelta(minutes=self.settings.cmd_expire_min)
        try:
            return self.commands.create(
                device_id=device_id, command=command, issued_by=issued_by, expires_at=expires_at
            )
        except ConflictError as exc:
            raise CommandPendingError(
                f"A '{command}' command is already pending for this device"
            ) from exc

    def issue_if_absent(self, device_id: int, command: str, issued_by: int | None) -> Any | None:
        """Used by status changes: an identical pending command is fine, not an error."""
        try:
            return self.issue(device_id, command, issued_by)
        except CommandPendingError:
            return None

    def deliver_pending(self, device_id: int) -> list[dict[str, Any]]:
        """Return pending commands oldest-first and mark them delivered."""
        self.expire_stale()
        pending = sorted(self.commands.pending_for_device(device_id), key=lambda c: c.command_id)
        self.commands.mark_delivered([c.command_id for c in pending])
        return [{"command_id": c.command_id, "command": c.command} for c in pending]

    def ack(self, device_id: int, command_id: int, result: str) -> Any:
        cmd = self.commands.get(command_id)
        if cmd is None or cmd.device_id != device_id:
            raise NotFoundError("Command not found for this device")
        failed = result.strip().lower().startswith(("fail", "error"))
        return self.commands.complete(command_id, result, failed=failed)

    def expire_stale(self) -> int:
        return self.commands.expire_stale(utcnow())
