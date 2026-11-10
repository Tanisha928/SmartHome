"""DeviceAuthService — exchange a device API key for a 15-minute device JWT (PLAN 5.2, S4)."""

from __future__ import annotations

import hmac
from typing import Any

from app.core.logging import get_logger
from app.core.ratelimit import device_token_limiter
from app.core.security import create_device_token, hash_api_key
from app.iot.errors import InvalidDeviceKeyError
from app.persistence.repositories.device_repo import DeviceRepository

log = get_logger(__name__)


class DeviceAuthService:
    def __init__(self, db: Any) -> None:
        self.devices = DeviceRepository(db)

    def issue_token(self, device_id: int, api_key: str) -> dict[str, Any]:
        device_token_limiter.check(f"device:{device_id}")
        device = self.devices.get_raw(device_id)
        presented = hash_api_key(api_key)
        valid = (
            device is not None
            and device.removed_at is None
            and device.key_revoked_at is None
            and hmac.compare_digest(presented, device.api_key_hash)
        )
        if not valid or device is None:
            log.warning("security.device_token_rejected", device_id=device_id)
            raise InvalidDeviceKeyError("Invalid device credentials")
        token, expires_in = create_device_token(
            device_id=device.device_id, house_id=device.house_id
        )
        return {"access_token": token, "token_type": "bearer", "expires_in": expires_in}
