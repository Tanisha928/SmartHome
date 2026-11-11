"""Resolve device, house, and global alert thresholds."""

from __future__ import annotations

from collections.abc import Mapping


class ThresholdResolver:
    """Small dependency-free resolver suitable for services and unit tests."""

    def __init__(
        self,
        *,
        device_overrides: Mapping[tuple[int, str], float] | None = None,
        house_overrides: Mapping[tuple[int, str], float] | None = None,
        global_overrides: Mapping[str, float] | None = None,
        default: float = 0.80,
    ) -> None:
        self.device_overrides = device_overrides or {}
        self.house_overrides = house_overrides or {}
        self.global_overrides = global_overrides or {}
        self.default = default

    def resolve(self, device_id: int, house_id: int, sound_type: str) -> float:
        """Resolve in the required device → house → global → default order."""

        value = self.device_overrides.get((device_id, sound_type))
        if value is None:
            value = self.house_overrides.get((house_id, sound_type))
        if value is None:
            value = self.global_overrides.get(sound_type)
        return self.default if value is None else float(value)
