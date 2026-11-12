"""Threshold resolution against current database state.

`ThresholdResolver` is a pure snapshot. Long-running processes (the model worker) must not
keep a snapshot from startup, or admin edits are ignored until restart, so this loads the
overrides on every call. It also honours the per-device threshold admins set on the device
itself (`devices.threshold`, A4 / PATCH /api/devices/{id}), which applies to every sound type.

Order: device+sound override → device threshold → house+sound → global+sound → default.
"""

from __future__ import annotations

from typing import Any

from app.alerts.threshold_resolver import ThresholdResolver
from app.persistence.repositories.device_repo import DeviceRepository
from app.persistence.repositories.threshold_repo import ThresholdRepository


class LiveThresholdResolver:
    def __init__(self, db: Any, *, default: float) -> None:
        self.db = db
        self.default = default

    def resolve(self, device_id: int, house_id: int, sound_type: str) -> float:
        overrides = ThresholdRepository(self.db).as_mappings()
        device_specific = overrides["device"].get((device_id, sound_type))
        if device_specific is not None:
            return float(device_specific)
        device = DeviceRepository(self.db).get_raw(device_id)
        if device is not None and device.threshold is not None:
            return float(device.threshold)
        return ThresholdResolver(
            house_overrides=overrides["house"],
            global_overrides=overrides["global"],
            default=self.default,
        ).resolve(device_id, house_id, sound_type)
