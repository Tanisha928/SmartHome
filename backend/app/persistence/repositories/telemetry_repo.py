"""TelemetryRepository (MongoDB) — full implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.persistence.mongo.client import sensor_telemetry


class TelemetryRepository:
    def write_heartbeat(self, **fields: Any) -> str:
        doc = {
            "device_id": fields["device_id"],
            "house_id": fields["house_id"],
            "reading_type": "heartbeat",
            "payload": {
                "wifi_rssi": fields.get("wifi_rssi"),
                "uptime_sec": fields.get("uptime_sec"),
                "buffer_depth": fields.get("buffer_depth"),
            },
            "processed": True,
            "ts": fields.get("ts") or datetime.now(UTC),
        }
        result = sensor_telemetry().insert_one(doc)
        return str(result.inserted_id)

    def latest(self, device_id: int) -> dict[str, Any] | None:
        doc = sensor_telemetry().find_one({"device_id": device_id}, sort=[("ts", -1)])
        if not doc:
            return None
        doc["id"] = str(doc.pop("_id"))
        return doc
