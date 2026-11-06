"""IngestService.handle — PLAN 4.5 exact behavior."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.config import get_settings
from app.core.deps import Claims
from app.core.errors import (
    AppError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
)
from app.core.logging import get_logger
from app.core.middleware import new_correlation_id
from app.persistence.pg.models import Device
from app.persistence.queue.publisher import QueuePublisher
from app.persistence.repositories.device_repo import DeviceRepository
from app.persistence.repositories.event_repo import EventRepository
from app.persistence.s3.clip_store import ClipStore

log = get_logger(__name__)

ALLOWED_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "video/mp4",
    "application/octet-stream",
}


class IngestService:
    def __init__(
        self,
        db: Any,
        *,
        clip_store: ClipStore | None = None,
        publisher: QueuePublisher | None = None,
    ) -> None:
        self.db = db
        self.devices = DeviceRepository(db)
        self.events = EventRepository(db)
        self.clips = clip_store or ClipStore()
        self.queue = publisher or QueuePublisher()
        self.settings = get_settings()

    def handle(
        self,
        *,
        claims: Claims,
        house_id: int,
        device_id: int,
        captured_at: datetime,
        clip_bytes: bytes,
        content_type: str,
        duration_sec: float | None,
        correlation_id: str | None,
        filename: str | None = None,
    ) -> tuple[dict[str, Any], int]:
        """Return (body, status_code)."""
        cid = correlation_id or new_correlation_id()

        max_bytes = self.settings.max_clip_mb * 1024 * 1024
        if len(clip_bytes) > max_bytes:
            raise PayloadTooLargeError(
                f"Clip exceeds {self.settings.max_clip_mb} MB",
                details={"max_mb": self.settings.max_clip_mb},
            )

        if not self._allowed_type(content_type, filename):
            raise AppError("Clip must be WAV or MP4", details={"error": "invalid_content_type"})

        if claims.type != "device":
            raise ForbiddenError("Device token required")
        if claims.device_id != device_id or claims.house_id != house_id:
            log.warning(
                "ingest_scope_violation",
                token_device=claims.device_id,
                token_house=claims.house_id,
                form_device=device_id,
                form_house=house_id,
                correlation_id=cid,
            )
            raise ForbiddenError("Device/house mismatch", details={"error": "scope_violation"})

        device = self.devices.get_raw(device_id)
        if device is None or device.removed_at is not None:
            raise NotFoundError("Device not found")
        if device.house_id != house_id:
            raise ForbiddenError("Device/house mismatch", details={"error": "scope_violation"})
        if device.status != "enabled":
            log.warning("ingest_device_disabled", device_id=device_id, correlation_id=cid)
            raise ForbiddenError("Device disabled", details={"error": "device_disabled"})

        existing = self.events.find(device_id, captured_at)
        if existing is not None:
            return {"event_id": existing.event_id, "duplicate": True}, 200

        event_id = self.events.allocate_id()
        try:
            s3_key = self.clips.put(house_id, event_id, clip_bytes, content_type, captured_at)
        except Exception:
            raise

        event, created = self.events.create_if_new(
            device_id,
            captured_at,
            s3_key,
            house_id,
            duration_sec,
            cid,
            event_id=event_id,
        )
        if not created:
            self.clips.delete(s3_key)
            return {"event_id": event.event_id, "duplicate": True}, 200

        message_id = self.queue.publish_inference_event(
            event_id=event.event_id,
            house_id=house_id,
            device_id=device_id,
            s3_key=s3_key,
            captured_at=captured_at,
            correlation_id=cid,
        )
        if message_id:
            from datetime import UTC

            event.last_published_at = datetime.now(UTC)
            self.db.flush()
            return {"event_id": event.event_id, "duplicate": False}, 202

        log.error("ingest_sqs_failed_keep_queued", event_id=event.event_id, correlation_id=cid)
        return {"event_id": event.event_id, "duplicate": False}, 202

    @staticmethod
    def _allowed_type(content_type: str, filename: str | None) -> bool:
        ct = (content_type or "").lower().split(";")[0].strip()
        if ct in ALLOWED_TYPES:
            if ct == "application/octet-stream" and filename:
                return filename.lower().endswith((".wav", ".mp4"))
            return ct != "application/octet-stream" or bool(filename)
        if filename:
            return filename.lower().endswith((".wav", ".mp4"))
        return False
