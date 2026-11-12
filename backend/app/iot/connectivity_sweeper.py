"""ConnectivitySweeper — mark devices offline after OFFLINE_AFTER_MIN without a heartbeat (S7)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.iot.command_queue import CommandQueue
from app.iot.events import publish_device_updated
from app.iot.timeutil import utcnow
from app.persistence.repositories.device_repo import DeviceRepository

log = get_logger(__name__)


class ConnectivitySweeper:
    def __init__(self, db: Any) -> None:
        self.db = db
        self.devices = DeviceRepository(db)
        self.commands = CommandQueue(db)

    def run(self) -> int:
        """Flip stale devices offline, expire old commands, commit. Returns devices changed."""
        cutoff = utcnow() - timedelta(minutes=get_settings().offline_after_min)
        stale_ids = self.devices.stale_online_ids(cutoff)
        changed = self.devices.mark_offline_stale(cutoff)
        expired = self.commands.expire_stale()
        for device_id in stale_ids:
            device = self.devices.get_raw(device_id)
            if device is not None:
                self.db.refresh(device)  # bulk UPDATE bypassed the identity map
                publish_device_updated(self.db, device)
        self.db.commit()  # events are delivered on this commit
        if changed or expired:
            log.info("connectivity_sweep", offline=changed, commands_expired=expired)
        return changed
