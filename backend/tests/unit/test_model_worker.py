from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from app.workers.model_worker import ModelWorker


class FakeQueue:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def receive_message(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            "Messages": [
                {
                    "Body": json.dumps(
                        {
                            "event_id": 9,
                            "house_id": 2,
                            "device_id": 4,
                            "s3_key": "clips/2/glass_break.wav",
                        }
                    ),
                    "ReceiptHandle": "receipt-1",
                }
            ]
        }

    def delete_message(self, *, ReceiptHandle: str, **_kwargs: Any) -> None:
        self.deleted.append(ReceiptHandle)


class FakeClipStore:
    def get_bytes(self, _key: str) -> bytes:
        return b"audio"


class FakeClassifier:
    def classify(self, _clip: bytes, *, filename: str = "") -> list[Any]:
        assert filename.endswith("glass_break.wav")
        return [SimpleNamespace(label="glass_break", confidence=0.95)]


class FakePolicy:
    def __init__(self) -> None:
        self.received: dict[str, Any] | None = None

    def handle(self, result: dict[str, Any]) -> str:
        self.received = result
        return "processed"


def test_worker_classifies_and_deletes_successful_message() -> None:
    queue = FakeQueue()
    policy = FakePolicy()
    worker = ModelWorker(
        queue=queue,
        queue_url="queue",
        clip_store=FakeClipStore(),
        classifier=FakeClassifier(),  # type: ignore[arg-type]
        policy_engine=policy,  # type: ignore[arg-type]
    )

    assert worker.run_once() == 1
    assert queue.deleted == ["receipt-1"]
    assert policy.received is not None
    assert policy.received["predictions"] == [{"label": "glass_break", "confidence": 0.95}]


def test_worker_keeps_failed_message_for_retry() -> None:
    queue = FakeQueue()

    class FailingPolicy:
        def handle(self, _result: dict[str, Any]) -> None:
            raise RuntimeError("policy unavailable")

    worker = ModelWorker(
        queue=queue,
        queue_url="queue",
        clip_store=FakeClipStore(),
        classifier=FakeClassifier(),  # type: ignore[arg-type]
        policy_engine=FailingPolicy(),  # type: ignore[arg-type]
    )

    assert worker.run_once() == 1
    assert queue.deleted == []
