"""StuckEventSweeper republishes and fails after max retries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.persistence.jobs.stuck_event_sweeper import StuckEventSweeper
from app.persistence.pg.models import Base, Device, Event, House, Room


class FakeQueue:
    def __init__(self) -> None:
        self.published: list[int] = []

    def publish_inference_event(self, **kwargs: Any) -> str | None:
        self.published.append(kwargs["event_id"])
        return "mid"


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
            device_id=1,
            room_id=1,
            house_id=1,
            device_type="audio",
            serial_no="S",
            api_key_hash="h",
        )
    )
    db.flush()
    return db


def test_sweeper_republish_and_fail() -> None:
    db = _db()
    old = datetime.now(UTC) - timedelta(minutes=10)
    db.add(
        Event(
            event_id=1,
            device_id=1,
            house_id=1,
            s3_key="k",
            captured_at=old,
            processing_state="queued",
            retry_count=0,
            last_published_at=None,
            correlation_id="c",
        )
    )
    db.add(
        Event(
            event_id=2,
            device_id=1,
            house_id=1,
            s3_key="k2",
            captured_at=old + timedelta(seconds=1),
            processing_state="queued",
            retry_count=5,
            last_published_at=old,
            correlation_id="c2",
        )
    )
    db.flush()
    q = FakeQueue()
    result = StuckEventSweeper(db, publisher=q, max_retries=5).run()  # type: ignore[arg-type]
    assert result["republished"] == 1
    assert result["failed"] == 1
    assert q.published == [1]
    assert db.get(Event, 2).processing_state == "failed"
