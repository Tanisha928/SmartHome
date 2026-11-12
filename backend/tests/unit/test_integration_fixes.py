"""Regressions for bugs found running the full stack (Postgres, LocalStack, worker, sweepers)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from botocore.exceptions import ClientError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.alerts.event_publisher import AlertEventHub, owner_safe
from app.alerts.live_thresholds import LiveThresholdResolver
from app.alerts.recipient_resolver import RecipientResolver
from app.persistence import events_bus
from app.persistence.pg.models import Base, Device, House, Room, ThresholdOverride
from app.persistence.s3.clip_store import ClipStore
from app.workers.model_worker import ModelWorker


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


# --- WebSocket hub ---------------------------------------------------------------------------


class FakeSocket:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def send_json(self, event: dict[str, Any]) -> None:
        self.events.append(event)


EVENT = {
    "type": "alert.created",
    "version": 1,
    "house_id": 1,
    "alert": {"alert_id": 5, "house_id": 1, "confidence": 0.93, "severity": "high"},
}


def test_admin_group_receives_every_house_owner_gets_safe_copy() -> None:
    async def scenario() -> None:
        hub = AlertEventHub()
        admin_all, admin_h1, owner_h1, owner_h2 = (FakeSocket() for _ in range(4))
        await hub.connect(None, admin_all, admin=True)  # type: ignore[arg-type]
        await hub.connect(1, admin_h1, admin=True)  # type: ignore[arg-type]
        await hub.connect(1, owner_h1)  # type: ignore[arg-type]
        await hub.connect(2, owner_h2)  # type: ignore[arg-type]

        await hub.publish(1, EVENT)

        assert admin_all.events == [EVENT]
        assert admin_h1.events == [EVENT]
        assert owner_h1.events[0]["alert"].get("confidence") is None
        assert owner_h1.events[0]["alert"]["severity"] == "high"
        assert owner_h2.events == []

    asyncio.run(scenario())


def test_owner_safe_does_not_mutate_original() -> None:
    owner_safe(EVENT)
    assert EVENT["alert"]["confidence"] == 0.93  # type: ignore[index]


# --- Event bus -------------------------------------------------------------------------------


def test_bus_publish_on_non_postgres_session_uses_local_handler(db: Session) -> None:
    received: list[dict[str, Any]] = []
    events_bus.set_local_handler(received.append)
    try:
        events_bus.publish(db, {"type": "device.updated", "house_id": 3})
    finally:
        events_bus.set_local_handler(None)
    assert received == [{"type": "device.updated", "house_id": 3}]


def test_bus_drops_oversized_payload_without_raising(db: Session) -> None:
    received: list[dict[str, Any]] = []
    events_bus.set_local_handler(received.append)
    try:
        events_bus.publish(db, {"type": "x", "blob": "a" * 10_000})
    finally:
        events_bus.set_local_handler(None)
    assert received == []


# --- Model worker ----------------------------------------------------------------------------


class Queue:
    def __init__(self, *, fail_receive: bool = False) -> None:
        self.fail_receive = fail_receive
        self.deleted: list[str] = []
        self.calls: list[str] = []

    def receive_message(self, **_kw: Any) -> dict[str, Any]:
        if self.fail_receive:
            raise ClientError(
                {"Error": {"Code": "AWS.SimpleQueueService.NonExistentQueue"}}, "ReceiveMessage"
            )
        body = {"event_id": 1, "house_id": 2, "device_id": 3, "s3_key": "clips/2/evt-1.wav"}
        return {"Messages": [{"Body": json.dumps(body), "ReceiptHandle": "r-1"}]}

    def delete_message(self, *, ReceiptHandle: str, **_kw: Any) -> None:
        self.calls.append("delete")
        self.deleted.append(ReceiptHandle)


class Clips:
    def get_clip(self, _key: str) -> tuple[bytes, str | None]:
        return b"audio", "glass_break-20261111T120000000Z.wav"


class Classifier:
    def __init__(self) -> None:
        self.filename = ""

    def classify(self, _clip: bytes, *, filename: str = "") -> list[Any]:
        self.filename = filename
        return [SimpleNamespace(label="glass_break", confidence=0.95)]


class Policy:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def handle(self, _result: dict[str, Any]) -> str:
        if self.fail:
            raise RuntimeError("db error")
        return "ok"


def _worker(queue: Queue, policy: Policy, calls: list[str], **kw: Any) -> ModelWorker:
    return ModelWorker(
        queue=queue,  # type: ignore[arg-type]
        queue_url="q",
        clip_store=Clips(),  # type: ignore[arg-type]
        classifier=kw.pop("classifier", Classifier()),  # type: ignore[arg-type]
        policy_engine=policy,  # type: ignore[arg-type]
        commit=lambda: calls.append("commit"),
        rollback=lambda: calls.append("rollback"),
        **kw,
    )


def test_worker_commits_before_deleting_message() -> None:
    queue = Queue()
    queue.calls = calls = []
    _worker(queue, Policy(), calls).run_once()
    assert calls == ["commit", "delete"]


def test_worker_rolls_back_and_keeps_message_on_failure() -> None:
    queue = Queue()
    queue.calls = calls = []
    _worker(queue, Policy(fail=True), calls).run_once()
    assert calls == ["rollback"]
    assert queue.deleted == []


def test_worker_survives_queue_errors_with_backoff() -> None:
    slept: list[float] = []
    worker = _worker(Queue(fail_receive=True), Policy(), [], sleep=slept.append)
    assert worker.run_once() == 0
    assert worker.run_once() == 0
    assert slept == [2.0, 4.0]


def test_worker_classifies_with_original_device_filename() -> None:
    classifier = Classifier()
    _worker(Queue(), Policy(), [], classifier=classifier).run_once()
    assert classifier.filename.startswith("glass_break-")


# --- Clip filename round trip ---------------------------------------------------------------


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}

    def put_object(self, **kw: Any) -> None:
        self.objects[kw["Key"]] = kw

    def get_object(self, **kw: Any) -> dict[str, Any]:
        obj = self.objects[kw["Key"]]
        return {"Body": SimpleNamespace(read=lambda: obj["Body"]), "Metadata": obj.get("Metadata")}


def test_clip_store_keeps_source_filename() -> None:
    from datetime import UTC, datetime

    store = ClipStore(client=FakeS3())  # type: ignore[arg-type]
    key = store.put(
        1, 9, b"x", "audio/wav", datetime(2026, 11, 11, tzinfo=UTC), source_filename="fall-1.wav"
    )
    assert key.endswith("evt-9.wav")
    assert store.get_clip(key) == (b"x", "fall-1.wav")


# --- Recipients ------------------------------------------------------------------------------


def test_owner_without_phone_gets_email_only() -> None:
    alert = SimpleNamespace(alert_category="emergency", severity="critical")
    owner = SimpleNamespace(user_id=1, role="owner", email="o@x.io", phone=None)
    channels = [r["channel"] for r in RecipientResolver().resolve(alert, [owner], [])]
    assert channels == ["email"]


# --- Thresholds ------------------------------------------------------------------------------


def _device(db: Session, threshold: Decimal | None) -> Device:
    house = House(address_line="1 A", postal_code="1", timezone="UTC")
    db.add(house)
    db.flush()
    room = Room(house_id=house.house_id, room_type="living", label="L")
    db.add(room)
    db.flush()
    device = Device(
        room_id=room.room_id,
        house_id=house.house_id,
        device_type="audio",
        serial_no="SN",
        api_key_hash="h",
        threshold=threshold,
    )
    db.add(device)
    db.flush()
    return device


def test_device_threshold_set_in_ui_is_applied(db: Session) -> None:
    device = _device(db, Decimal("0.95"))
    resolver = LiveThresholdResolver(db, default=0.80)
    assert resolver.resolve(device.device_id, device.house_id, "glass_break") == 0.95


def test_threshold_edits_apply_without_restart(db: Session) -> None:
    device = _device(db, None)
    resolver = LiveThresholdResolver(db, default=0.80)
    assert resolver.resolve(device.device_id, device.house_id, "fall") == 0.80
    db.add(ThresholdOverride(scope="global", scope_id=None, sound_type="fall", threshold=0.6))
    db.flush()
    assert resolver.resolve(device.device_id, device.house_id, "fall") == 0.6
    db.add(
        ThresholdOverride(
            scope="device", scope_id=device.device_id, sound_type="fall", threshold=0.7
        )
    )
    db.flush()
    assert resolver.resolve(device.device_id, device.house_id, "fall") == 0.7


# --- FR-19: inference logs carry model + features --------------------------------------------


def _wav(seconds: float = 0.5) -> bytes:
    import io
    import math
    import struct
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16_000)
        n = int(16_000 * seconds)
        w.writeframes(b"".join(struct.pack("<h", int(16000 * math.sin(i / 10))) for i in range(n)))
    return buf.getvalue()


def test_clip_features_for_wav_and_other_formats() -> None:
    from app.ml.preprocess import clip_features

    features = clip_features(_wav(0.5))
    assert features["duration_sec"] == 0.5
    assert 0 < float(features["rms"]) < 1
    assert -7 < float(features["peak_db"]) < 0
    assert clip_features(b"not audio") == {"size_bytes": 9}


def test_worker_result_includes_model_and_features() -> None:
    class Recorder(Policy):
        result: dict[str, Any] = {}

        def handle(self, result: dict[str, Any]) -> str:
            Recorder.result = result
            return "ok"

    class WavClips:
        def get_clip(self, _key: str) -> tuple[bytes, str | None]:
            return _wav(0.25), "fall-1.wav"

    from app.ml.classifier import MockClassifier

    worker = ModelWorker(
        queue=Queue(),  # type: ignore[arg-type]
        queue_url="q",
        clip_store=WavClips(),  # type: ignore[arg-type]
        classifier=MockClassifier(),
        policy_engine=Recorder(),  # type: ignore[arg-type]
    )
    worker.run_once()
    assert Recorder.result["model"]["name"] == "mock-classifier"
    assert Recorder.result["model"]["version"] == "mock-1"
    assert Recorder.result["model"]["runtime_ms"] >= 0
    assert Recorder.result["features"]["duration_sec"] == 0.25
    assert Recorder.result["predictions"][0]["label"] == "fall"
