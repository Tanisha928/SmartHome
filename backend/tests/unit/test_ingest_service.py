"""IngestService business rules from PLAN 4.5 / table 4.4."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import Claims
from app.core.errors import DependencyUnavailableError, ForbiddenError, PayloadTooLargeError
from app.persistence.ingest.service import IngestService
from app.persistence.pg.models import Base, Device, House, Room


class FakeClipStore:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def put(
        self,
        house_id: int,
        event_id: int,
        data: bytes,
        content_type: str,
        captured_at: datetime,
        source_filename: str | None = None,
    ) -> str:
        if self.fail:
            raise DependencyUnavailableError(
                "S3 storage unavailable", details={"error": "storage_unavailable"}
            )
        key = f"clips/{house_id}/evt-{event_id}.wav"
        self.objects[key] = data
        return key

    def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.objects.pop(key, None)


class FakeQueue:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.published: list[dict[str, Any]] = []

    def publish_inference_event(self, **kwargs: Any) -> str | None:
        if self.fail:
            return None
        self.published.append(kwargs)
        return "mid-1"


def _db():
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
            device_id=5,
            room_id=1,
            house_id=1,
            device_type="audio",
            serial_no="SN-1",
            api_key_hash="h",
            status="enabled",
        )
    )
    db.flush()
    return db


def _claims() -> Claims:
    return Claims(sub=5, type="device", device_id=5, house_id=1)


def test_ingest_happy_path_202() -> None:
    db = _db()
    svc = IngestService(db, clip_store=FakeClipStore(), publisher=FakeQueue())  # type: ignore[arg-type]
    body, status = svc.handle(
        claims=_claims(),
        house_id=1,
        device_id=5,
        captured_at=datetime(2026, 11, 6, 12, 0, tzinfo=UTC),
        clip_bytes=b"RIFF....wav",
        content_type="audio/wav",
        duration_sec=1.5,
        correlation_id="c-1",
        filename="clip.wav",
    )
    assert status == 202
    assert body["duplicate"] is False
    assert body["event_id"]


def test_ingest_413_too_large(monkeypatch: Any) -> None:
    monkeypatch.setenv("MAX_CLIP_MB", "1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    db = _db()
    svc = IngestService(db, clip_store=FakeClipStore(), publisher=FakeQueue())  # type: ignore[arg-type]
    with pytest.raises(PayloadTooLargeError):
        svc.handle(
            claims=_claims(),
            house_id=1,
            device_id=5,
            captured_at=datetime(2026, 11, 6, 12, 1, tzinfo=UTC),
            clip_bytes=b"x" * (2 * 1024 * 1024),
            content_type="audio/wav",
            duration_sec=None,
            correlation_id="c",
            filename="big.wav",
        )
    get_settings.cache_clear()


def test_ingest_403_mismatch() -> None:
    db = _db()
    svc = IngestService(db, clip_store=FakeClipStore(), publisher=FakeQueue())  # type: ignore[arg-type]
    bad = Claims(sub=5, type="device", device_id=5, house_id=99)
    with pytest.raises(ForbiddenError):
        svc.handle(
            claims=bad,
            house_id=1,
            device_id=5,
            captured_at=datetime(2026, 11, 6, 12, 2, tzinfo=UTC),
            clip_bytes=b"RIFF",
            content_type="audio/wav",
            duration_sec=None,
            correlation_id="c",
            filename="a.wav",
        )


def test_ingest_duplicate_200() -> None:
    db = _db()
    clips = FakeClipStore()
    svc = IngestService(db, clip_store=clips, publisher=FakeQueue())  # type: ignore[arg-type]
    captured = datetime(2026, 11, 6, 12, 3, tzinfo=UTC)
    first, s1 = svc.handle(
        claims=_claims(),
        house_id=1,
        device_id=5,
        captured_at=captured,
        clip_bytes=b"RIFF1",
        content_type="audio/wav",
        duration_sec=None,
        correlation_id="c1",
        filename="a.wav",
    )
    second, s2 = svc.handle(
        claims=_claims(),
        house_id=1,
        device_id=5,
        captured_at=captured,
        clip_bytes=b"RIFF2",
        content_type="audio/wav",
        duration_sec=None,
        correlation_id="c2",
        filename="a.wav",
    )
    assert s1 == 202 and s2 == 200
    assert second["duplicate"] is True
    assert second["event_id"] == first["event_id"]
    assert len(clips.objects) == 1


def test_ingest_s3_failure_503() -> None:
    db = _db()
    svc = IngestService(db, clip_store=FakeClipStore(fail=True), publisher=FakeQueue())  # type: ignore[arg-type]
    with pytest.raises(DependencyUnavailableError):
        svc.handle(
            claims=_claims(),
            house_id=1,
            device_id=5,
            captured_at=datetime(2026, 11, 6, 12, 4, tzinfo=UTC),
            clip_bytes=b"RIFF",
            content_type="audio/wav",
            duration_sec=None,
            correlation_id="c",
            filename="a.wav",
        )


def test_ingest_sqs_failure_still_202() -> None:
    db = _db()
    svc = IngestService(db, clip_store=FakeClipStore(), publisher=FakeQueue(fail=True))  # type: ignore[arg-type]
    body, status = svc.handle(
        claims=_claims(),
        house_id=1,
        device_id=5,
        captured_at=datetime(2026, 11, 6, 12, 5, tzinfo=UTC),
        clip_bytes=b"RIFF",
        content_type="audio/wav",
        duration_sec=None,
        correlation_id="c",
        filename="a.wav",
    )
    assert status == 202
    assert body["duplicate"] is False
