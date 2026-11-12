"""HeartbeatService — device liveness, telemetry, command delivery, config sync (PLAN 6.1, S5)."""

from __future__ import annotations

from typing import Any, Protocol

from app.core.deps import Claims
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.iot.command_queue import CommandQueue
from app.iot.errors import DeviceMismatchError, DeviceRemovedError
from app.iot.events import publish_device_updated
from app.iot.timeutil import utcnow
from app.persistence.repositories.device_repo import DeviceRepository

log = get_logger(__name__)


class TelemetrySink(Protocol):
    def write_heartbeat(self, **fields: Any) -> str: ...


def device_config(device: Any) -> dict[str, Any]:
    return {
        "capture_enabled": device.status == "enabled",
        "threshold": float(device.threshold) if device.threshold is not None else None,
        "version": int(device.config_version or 1),
    }


class HeartbeatService:
    def __init__(self, db: Any, telemetry: TelemetrySink | None = None) -> None:
        self.devices = DeviceRepository(db)
        self.commands = CommandQueue(db)
        self._telemetry = telemetry

    @property
    def telemetry(self) -> TelemetrySink:
        if self._telemetry is None:
            from app.persistence.repositories.telemetry_repo import TelemetryRepository

            self._telemetry = TelemetryRepository()
        return self._telemetry

    def handle(
        self,
        claims: Claims,
        device_id: int,
        *,
        wifi_rssi: int,
        uptime_sec: int,
        buffer_depth: int,
        config_version: int,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        if claims.device_id != device_id:
            log.warning(
                "security.device_mismatch",
                token_device=claims.device_id,
                path_device=device_id,
                correlation_id=correlation_id,
            )
            raise DeviceMismatchError("Token does not match device")

        device = self.devices.get_raw(device_id)
        if device is None:
            raise NotFoundError("Device not found")
        if device.removed_at is not None or device.key_revoked_at is not None:
            raise DeviceRemovedError("Device has been removed")

        first_call = device.last_heartbeat is None
        was_online = device.conn_state == "online"
        now = utcnow()
        device = self.devices.update(
            device_id, last_heartbeat=now, wifi_rssi=wifi_rssi, conn_state="online"
        )

        try:
            self.telemetry.write_heartbeat(
                device_id=device_id,
                house_id=device.house_id,
                wifi_rssi=wifi_rssi,
                uptime_sec=uptime_sec,
                buffer_depth=buffer_depth,
                ts=now,
            )
        except Exception as exc:  # telemetry is best-effort; liveness must still update
            log.warning("telemetry_write_failed", device_id=device_id, error=str(exc))

        commands = self.commands.deliver_pending(device_id)
        response: dict[str, Any] = {"commands": commands}
        if first_call or config_version != device.config_version:
            response["config"] = device_config(device)
        if not was_online:
            publish_device_updated(self.devices.db, device)
        return response

    def ack(self, claims: Claims, device_id: int, command_id: int, result: str) -> dict[str, Any]:
        if claims.device_id != device_id:
            log.warning(
                "security.device_mismatch", token_device=claims.device_id, path_device=device_id
            )
            raise DeviceMismatchError("Token does not match device")
        cmd = self.commands.ack(device_id, command_id, result)
        device = self.devices.get_raw(device_id)
        if device is not None:
            publish_device_updated(self.devices.db, device)
        return {"command_id": cmd.command_id, "status": cmd.status}
