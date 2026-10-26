"""QueuePublisher message body shape."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.persistence.queue.publisher import QueuePublisher


class FakeSQS:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def send_message(self, **kwargs: Any) -> dict[str, str]:
        self.messages.append(kwargs)
        return {"MessageId": "mid-1"}

    def get_queue_attributes(self, **kwargs: Any) -> dict[str, Any]:
        return {"Attributes": {"ApproximateNumberOfMessages": "0"}}


def test_publish_body_shape(monkeypatch: Any) -> None:
    monkeypatch.setenv("SQS_QUEUE_URL", "http://local/q")
    from app.core.config import get_settings

    get_settings.cache_clear()
    fake = FakeSQS()
    pub = QueuePublisher(client=fake)  # type: ignore[arg-type]
    mid = pub.publish_inference_event(
        event_id=10,
        house_id=2,
        device_id=5,
        s3_key="clips/2/2026/10/25/evt-10.wav",
        captured_at=datetime(2026, 10, 25, 15, 0, tzinfo=UTC),
        correlation_id="c-abc",
    )
    assert mid == "mid-1"
    body = json.loads(fake.messages[0]["MessageBody"])
    assert body == {
        "event_id": 10,
        "house_id": 2,
        "device_id": 5,
        "s3_key": "clips/2/2026/10/25/evt-10.wav",
        "captured_at": "2026-10-25T15:00:00Z",
        "correlation_id": "c-abc",
    }
    get_settings.cache_clear()
