"""TelemetryRepository (MongoDB) skeleton."""

from __future__ import annotations

from typing import Any


class TelemetryRepository:
    def write_heartbeat(self, **fields: Any) -> str:
        raise NotImplementedError

    def latest(self, device_id: int) -> dict[str, Any] | None:
        raise NotImplementedError
