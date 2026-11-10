"""Smoke: simulate 50 clips/min throughput against in-memory fakes (no loss)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import Claims
from app.persistence.ingest.service import IngestService
from app.persistence.pg.models import Base, Device, House, Room


class FakeClipStore:
    def __init__(self) -> None:
        self.count = 0

    def put(self, house_id, event_id, data, content_type, captured_at):  # type: ignore[no-untyped-def]
        self.count += 1
        return f"clips/{house_id}/evt-{event_id}.wav"

    def delete(self, key: str) -> None:
        return None


class FakeQueue:
    def __init__(self) -> None:
        self.count = 0

    def publish_inference_event(self, **kwargs):  # type: ignore[no-untyped-def]
        self.count += 1
        return f"mid-{self.count}"


def test_fifty_clips_no_loss() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(House(house_id=1, timezone="UTC", address_line="a", postal_code="1"))
    db.add(Room(room_id=1, house_id=1, room_type="living", label="L"))
    db.add(
        Device(
            device_id=1,
            room_id=1,
            house_id=1,
            device_type="audio",
            serial_no="S",
            api_key_hash="h",
            status="enabled",
        )
    )
    db.flush()

    clips = FakeClipStore()
    queue = FakeQueue()
    svc = IngestService(db, clip_store=clips, publisher=queue)  # type: ignore[arg-type]
    claims = Claims(sub=1, type="device", device_id=1, house_id=1)
    base = datetime(2026, 11, 9, 17, 0, tzinfo=UTC)
    ok = 0
    for i in range(50):
        body, status = svc.handle(
            claims=claims,
            house_id=1,
            device_id=1,
            captured_at=base + timedelta(seconds=i),
            clip_bytes=b"RIFF",
            content_type="audio/wav",
            duration_sec=0.5,
            correlation_id=f"c-{i}",
            filename="c.wav",
        )
        assert status == 202
        assert body["duplicate"] is False
        ok += 1
    assert ok == 50
    assert clips.count == 50
    assert queue.count == 50
