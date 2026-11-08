"""StuckEventSweeper — republish queued events older than 5 minutes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.persistence.queue.publisher import QueuePublisher
from app.persistence.repositories.event_repo import EventRepository

log = get_logger(__name__)


class StuckEventSweeper:
    def __init__(
        self,
        db: Any,
        *,
        publisher: QueuePublisher | None = None,
        max_retries: int = 5,
        stale_after_min: int = 5,
    ) -> None:
        self.events = EventRepository(db)
        self.queue = publisher or QueuePublisher()
        self.max_retries = max_retries
        self.stale_after = timedelta(minutes=stale_after_min)

    def run(self) -> dict[str, int]:
        cutoff = datetime.now(UTC) - self.stale_after
        stale = self.events.list_stale_queued(cutoff)
        republished = 0
        failed = 0
        for event in stale:
            updated = self.events.increment_retry(event.event_id)
            if updated.retry_count > self.max_retries:
                self.events.set_failed(event.event_id)
                failed += 1
                continue
            mid = self.queue.publish_inference_event(
                event_id=event.event_id,
                house_id=event.house_id,
                device_id=event.device_id,
                s3_key=event.s3_key or "",
                captured_at=event.captured_at,
                correlation_id=event.correlation_id or "",
            )
            if mid:
                republished += 1
            else:
                log.warning("sweeper_publish_failed", event_id=event.event_id)
        return {"examined": len(stale), "republished": republished, "failed": failed}
