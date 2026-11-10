"""DeviceService — register, list, update, remove, rotate key, house cascade (S2/S3/S8)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.deps import Claims
from app.core.errors import ForbiddenError
from app.core.logging import get_logger
from app.core.security import generate_device_api_key
from app.iot.command_queue import CommandQueue
from app.iot.errors import DuplicateSerialError, InvalidThresholdError
from app.iot.events import publish_device_updated
from app.iot.room_service import ensure_house_access
from app.iot.timeutil import iso_z, utcnow
from app.persistence.repositories.device_repo import DeviceRepository
from app.persistence.repositories.house_repo import HouseRepository
from app.persistence.repositories.room_repo import RoomRepository

log = get_logger(__name__)

THRESHOLD_MIN = 0.50
THRESHOLD_MAX = 0.99
ADMIN_FIELDS = {"label", "threshold", "room_id", "status"}
OWNER_FIELDS = {"status"}


def serialize_device(device: Any, *, for_admin: bool) -> dict[str, Any]:
    body: dict[str, Any] = {
        "device_id": device.device_id,
        "house_id": device.house_id,
        "room_id": device.room_id,
        "device_type": device.device_type,
        "serial_no": device.serial_no,
        "label": device.label,
        "status": device.status,
        "conn_state": device.conn_state,
        "wifi_rssi": device.wifi_rssi,
        "last_heartbeat": iso_z(device.last_heartbeat) if device.last_heartbeat else None,
        "config_version": device.config_version,
    }
    if for_admin:
        body["threshold"] = float(device.threshold) if device.threshold is not None else None
        body["api_key_prefix"] = device.api_key_prefix
        body["key_revoked_at"] = iso_z(device.key_revoked_at) if device.key_revoked_at else None
    return body


class DeviceService:
    def __init__(self, db: Any) -> None:
        self.db = db
        self.devices = DeviceRepository(db)
        self.rooms = RoomRepository(db)
        self.houses = HouseRepository(db)
        self.commands = CommandQueue(db)

    # -- registration -------------------------------------------------------------------------

    def register(
        self,
        claims: Claims,
        *,
        room_id: int,
        device_type: str,
        serial_no: str,
        label: str | None,
    ) -> dict[str, Any]:
        """Create a device; return it plus the raw API key (shown exactly once)."""
        room = self.rooms.get(room_id, claims)  # 404 / 403
        ensure_house_access(claims, room.house_id)
        serial = serial_no.strip()
        if self.devices.find_by_serial(serial) is not None:
            raise DuplicateSerialError("A device with this serial number is already registered")
        raw_key, key_hash, prefix = generate_device_api_key()
        device = self.devices.create(
            room_id=room.room_id,
            house_id=room.house_id,
            device_type=device_type,
            serial_no=serial,
            label=label,
            conn_state="offline",
            api_key_hash=key_hash,
            api_key_prefix=prefix,
        )
        log.info("device_registered", device_id=device.device_id, house_id=device.house_id)
        publish_device_updated(device)
        return {
            **serialize_device(device, for_admin=claims.role == "admin"),
            "api_key": raw_key,
        }

    # -- reads --------------------------------------------------------------------------------

    def list(
        self, claims: Claims, filters: dict[str, Any], page: int, page_size: int
    ) -> dict[str, Any]:
        if filters.get("house_id") is not None:
            ensure_house_access(claims, int(filters["house_id"]))
        result = self.devices.list(filters, page, claims, page_size=page_size)
        admin = claims.role == "admin"
        return {**result, "items": [serialize_device(d, for_admin=admin) for d in result["items"]]}

    def get(self, claims: Claims, device_id: int) -> dict[str, Any]:
        return serialize_device(
            self.devices.get(device_id, claims), for_admin=claims.role == "admin"
        )

    # -- writes -------------------------------------------------------------------------------

    def update(self, claims: Claims, device_id: int, changes: dict[str, Any]) -> dict[str, Any]:
        device = self.devices.get(device_id, claims)  # 404 / 403
        allowed = ADMIN_FIELDS if claims.role == "admin" else OWNER_FIELDS
        forbidden = set(changes) - allowed
        if forbidden:
            raise ForbiddenError(
                "Not allowed to change these fields", details={"fields": sorted(forbidden)}
            )

        updates: dict[str, Any] = {}
        if "threshold" in changes and changes["threshold"] is not None:
            value = float(changes["threshold"])
            if not THRESHOLD_MIN <= value <= THRESHOLD_MAX:
                raise InvalidThresholdError(
                    f"threshold must be between {THRESHOLD_MIN} and {THRESHOLD_MAX}"
                )
            updates["threshold"] = Decimal(f"{value:.2f}")
        if "room_id" in changes and changes["room_id"] is not None:
            room = self.rooms.get(int(changes["room_id"]), claims)
            if room.house_id != device.house_id:
                raise ForbiddenError("Room belongs to a different house")
            updates["room_id"] = room.room_id
        if changes.get("label") is not None:
            updates["label"] = changes["label"]

        status_changed = False
        if changes.get("status") is not None and changes["status"] != device.status:
            updates["status"] = changes["status"]
            status_changed = True

        if updates:
            # Any config-visible change bumps the version so the edge re-syncs on next heartbeat.
            updates["config_version"] = int(device.config_version or 1) + 1
            device = self.devices.update(device_id, **updates)
        if status_changed:
            self.commands.issue_if_absent(
                device_id, "enable" if device.status == "enabled" else "disable", claims.user_id
            )
        if updates:
            publish_device_updated(device)
        return serialize_device(device, for_admin=claims.role == "admin")

    def remove(self, claims: Claims, device_id: int) -> None:
        device = self.devices.get(device_id, claims)
        self.devices.soft_remove(device.device_id)
        log.info("device_removed", device_id=device_id, actor=claims.user_id)

    def rotate_key(self, claims: Claims, device_id: int) -> dict[str, Any]:
        """Admin only. New key returned once; the previous key stops working immediately."""
        self.devices.get(device_id, claims)
        raw_key, key_hash, prefix = generate_device_api_key()
        device = self.devices.update(device_id, api_key_hash=key_hash, api_key_prefix=prefix)
        # `update` skips None, so clear a prior revoke explicitly.
        device.key_revoked_at = None
        self.db.flush()
        log.info("device_key_rotated", device_id=device_id, actor=claims.user_id)
        return {**serialize_device(device, for_admin=True), "api_key": raw_key}

    def issue_command(self, claims: Claims, device_id: int, command: str) -> dict[str, Any]:
        self.devices.get(device_id, claims)
        if claims.role != "admin" and command not in ("enable", "disable"):
            raise ForbiddenError("Owners may only enable or disable devices")
        cmd = self.commands.issue(device_id, command, claims.user_id)
        return {"command_id": cmd.command_id, "command": cmd.command, "status": cmd.status}

    # -- house cascade ------------------------------------------------------------------------

    def set_house_status(self, claims: Claims, house_id: int, status: str) -> dict[str, Any]:
        """Disable/enable a house and all its devices in one transaction (S8).

        On any failure the whole unit of work is rolled back and the error re-raised.
        """
        device_status = "enabled" if status == "active" else "disabled"
        command = "enable" if status == "active" else "disable"
        changed: list[Any] = []
        try:
            self.houses.get(house_id, claims)  # 404 / scope (admin-only route anyway)
            self.houses.set_status(house_id, status)
            for device in self.devices.list_for_house(house_id):
                if device.status == device_status:
                    continue
                device = self.devices.update(
                    device.device_id,
                    status=device_status,
                    config_version=int(device.config_version or 1) + 1,
                )
                self.commands.issue_if_absent(device.device_id, command, claims.user_id)
                changed.append(device)
            self.db.flush()
        except Exception:
            self.db.rollback()
            log.error("house_cascade_rolled_back", house_id=house_id, target=status)
            raise
        for device in changed:
            publish_device_updated(device)
        return {
            "house_id": house_id,
            "status": status,
            "devices_updated": len(changed),
            "at": iso_z(utcnow()),
        }
