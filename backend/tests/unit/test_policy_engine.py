from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.alerts.policy_engine import PolicyEngine
from app.alerts.threshold_resolver import ThresholdResolver
from app.ml.classifier import MockClassifier
from app.workers.model_worker import ModelWorker


class FakeEvent:
    def __init__(self) -> None:
        self.event_id = 9
        self.house_id = 2
        self.device_id = 4
        self.correlation_id = "cid-9"
        self.processing_state = "queued"
        self.decision: str | None = None


class FakeEvents:
    def __init__(self) -> None:
        self.event = FakeEvent()

    def get(self, event_id: int) -> FakeEvent | None:
        return self.event if event_id == self.event.event_id else None

    def mark_scored(self, _event_id: int, decision: str) -> None:
        self.event.processing_state = "scored"
        self.event.decision = decision


class FakeDevices:
    def get_raw(self, _device_id: int) -> Any:
        return SimpleNamespace(room_id=8)


class FakeAlerts:
    def __init__(self, recent: Any | None = None, events: FakeEvents | None = None) -> None:
        self.recent = recent
        self.events = events
        self.created: list[dict[str, Any]] = []
        self.suppressed: list[int] = []

    def find_recent(self, _sound_type: str, _room_id: int, _within_sec: int) -> Any | None:
        return self.recent

    def increment_suppressed(self, alert_id: int) -> None:
        self.suppressed.append(alert_id)

    def create_with_history_and_mark_event_scored(self, **kwargs: Any) -> Any:
        self.created.append(kwargs)
        if self.events is not None:
            self.events.mark_scored(int(kwargs["event_id"]), "alert_created")
        return SimpleNamespace(alert_id=101)


class FakeLogs:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []

    def write(self, document: dict[str, Any]) -> str:
        self.documents.append(document)
        return str(len(self.documents))


def make_engine(
    *, recent: Any | None = None
) -> tuple[PolicyEngine, FakeEvents, FakeAlerts, FakeLogs]:
    events = FakeEvents()
    alerts = FakeAlerts(recent, events)
    logs = FakeLogs()
    engine = PolicyEngine(
        event_repository=events,
        device_repository=FakeDevices(),
        alert_repository=alerts,
        inference_log_repository=logs,
        threshold_resolver=ThresholdResolver(default=0.80),
    )
    return engine, events, alerts, logs


@pytest.mark.parametrize(
    ("predictions", "decision"),
    [
        ([{"label": "unknown", "confidence": 0.99}], "unknown_label"),
        ([{"label": "glass_break", "confidence": 0.79}], "below_threshold"),
    ],
)
def test_non_alert_policy_outcomes_are_scored_and_logged(
    predictions: list[dict[str, Any]], decision: str
) -> None:
    engine, events, alerts, logs = make_engine()
    result = engine.handle({"event_id": 9, "predictions": predictions})

    assert result.decision == decision
    assert events.event.processing_state == "scored"
    assert logs.documents[-1]["policy"]["decision"] == decision
    assert alerts.created == []


def test_duplicate_policy_outcome_is_logged_and_suppressed() -> None:
    engine, _events, alerts, logs = make_engine(recent=SimpleNamespace(alert_id=55))
    result = engine.handle(
        {"event_id": 9, "predictions": [{"label": "glass_break", "confidence": 0.95}]}
    )

    assert result.decision == "duplicate_suppressed"
    assert alerts.suppressed == [55]
    assert logs.documents[-1]["policy"]["decision"] == "duplicate_suppressed"


def test_alert_creation_is_logged_with_alert_id() -> None:
    engine, events, alerts, logs = make_engine()
    result = engine.handle(
        {
            "event_id": 9,
            "s3_key": "clips/2/glass_break.wav",
            "predictions": [{"label": "glass_break", "confidence": 0.95}],
        }
    )

    assert result.alert_id == 101
    assert events.event.decision == "alert_created"
    assert alerts.created[0]["severity"] == "high"
    assert logs.documents[-1]["policy"] == {
        "threshold": 0.80,
        "decision": "alert_created",
        "alert_id": 101,
    }


def test_redelivery_is_idempotent() -> None:
    engine, events, alerts, logs = make_engine()
    first = engine.handle(
        {"event_id": 9, "predictions": [{"label": "glass_break", "confidence": 0.95}]}
    )
    second = engine.handle(
        {"event_id": 9, "predictions": [{"label": "glass_break", "confidence": 0.95}]}
    )

    assert first.decision == "alert_created"
    assert second.decision == "alert_created"
    assert len(alerts.created) == 1
    assert len(logs.documents) == 1


def test_queued_message_flows_through_worker_and_policy() -> None:
    engine, events, alerts, logs = make_engine()

    class Queue:
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
                        "ReceiptHandle": "receipt-e2e",
                    }
                ]
            }

        def delete_message(self, *, ReceiptHandle: str, **_kwargs: Any) -> None:
            self.deleted.append(ReceiptHandle)

    class ClipStore:
        def get_bytes(self, _key: str) -> bytes:
            return b"audio"

    queue = Queue()
    worker = ModelWorker(
        queue=queue,  # type: ignore[arg-type]
        queue_url="queue",
        clip_store=ClipStore(),  # type: ignore[arg-type]
        classifier=MockClassifier(),
        policy_engine=engine,
    )

    assert worker.run_once() == 1
    assert queue.deleted == ["receipt-e2e"]
    assert events.event.decision == "alert_created"
    assert len(alerts.created) == 1
    assert logs.documents[-1]["policy"]["decision"] == "alert_created"
