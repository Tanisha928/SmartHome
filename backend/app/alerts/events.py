"""Alert serialization and `alert.created` / `alert.updated` publishing (PLAN 8.8)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.logging import get_logger
from app.persistence.events_bus import publish

log = get_logger(__name__)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def serialize_alert(alert: Any, *, owner_view: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "alert_id": alert.alert_id,
        "event_id": alert.event_id,
        "house_id": alert.house_id,
        "room_id": alert.room_id,
        "device_id": alert.device_id,
        "alert_category": alert.alert_category,
        "sound_type": alert.sound_type,
        "severity": alert.severity,
        "state": alert.state,
        "suppressed_count": alert.suppressed_count,
        "version": alert.version,
        "created_at": iso(alert.created_at),
        "updated_at": iso(alert.updated_at),
    }
    if not owner_view:
        payload["confidence"] = float(alert.confidence) if alert.confidence is not None else None
    return payload


def alert_event(event_type: str, alert: Any) -> dict[str, Any]:
    return {
        "type": event_type,
        "version": int(alert.version or 1),
        "house_id": int(alert.house_id),
        "alert": serialize_alert(alert, owner_view=False),  # hub strips fields for owners
    }


def publish_alert(db: Any, event_type: str, alert: Any) -> None:
    """Publish on `db`'s transaction; delivered to WebSocket clients when it commits.

    Best-effort: a malformed alert must never break the state change it reports on.
    """
    try:
        event = alert_event(event_type, alert)
    except Exception as exc:
        log.warning("alert_event_build_failed", type=event_type, error=str(exc))
        return
    publish(db, event)


def bus_publisher(db: Any) -> Any:
    """Adapter for PolicyEngine(publisher=...), which calls publisher(type, alert)."""

    def _publish(event_type: str, alert: Any) -> None:
        publish_alert(db, event_type, alert)

    return _publish
