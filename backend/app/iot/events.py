"""`device.updated` event publishing (PLAN 6.2 / FR-4).

The WebSocket hub lives in `app.alerts.event_publisher` (Vritika, Phase 5). Until it lands,
events are logged. Tests can swap the sink with `set_sink`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.logging import get_logger
from app.iot.timeutil import iso_z

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


def publish_device_updated(device: Any) -> None:
    """Best-effort fan-out; never raises into the caller."""
    event = device_event_payload(device)
    try:
        if _sink is not None:
            _sink(event)
            return
        from app.alerts import event_publisher  # type: ignore[attr-defined]

        event_publisher.publish(event)
    except Exception as exc:  # hub not available yet, or publish failed
        log.info("device_updated", device_id=event["device"]["device_id"], hub_error=str(exc))
