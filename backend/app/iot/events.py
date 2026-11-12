"""`device.updated` event publishing (PLAN 6.2 / FR-4).

Events go on the caller's DB session through the Postgres event bus, so they are delivered to
WebSocket clients when that transaction commits — from the API, or from the sweepers process.
Tests can capture events with `set_sink`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.logging import get_logger
from app.iot.timeutil import iso_z
from app.persistence.events_bus import publish

log = get_logger(__name__)

Sink = Callable[[dict[str, Any]], None]
_sink: Sink | None = None


def set_sink(sink: Sink | None) -> None:
    global _sink
    _sink = sink


def device_event_payload(device: Any) -> dict[str, Any]:
    return {
        "type": "device.updated",
        "version": int(device.config_version or 1),
        "house_id": int(device.house_id),
        "device": {
            "device_id": device.device_id,
            "room_id": device.room_id,
            "label": device.label,
            "status": device.status,
            "conn_state": device.conn_state,
            "wifi_rssi": device.wifi_rssi,
            "last_heartbeat": iso_z(device.last_heartbeat) if device.last_heartbeat else None,
        },
    }


def publish_device_updated(db: Any, device: Any) -> None:
    """Best-effort; never raises into the caller. Delivered when `db` commits."""
    event = device_event_payload(device)
    if _sink is not None:
        _sink(event)
        return
    publish(db, event)
