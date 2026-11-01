"""create_if_new uniqueness and transition conflict helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import StateConflictError
from app.persistence.pg.models import Base, Device, Event, House, Room, User
from app.persistence.repositories.alert_repo import AlertRepository
from app.persistence.repositories.event_repo import EventRepository


def _db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(user_id=1, email="a@x.com", password_hash="x", role="admin"))
    db.add(House(house_id=1, timezone="UTC", address_line="1", postal_code="1"))
    db.add(Room(room_id=1, house_id=1, room_type="living", label="L"))
    db.add(
        Device(
            device_id=1,
            room_id=1,
            house_id=1,
            device_type="audio",
            serial_no="S1",
            api_key_hash="h",
        )
    )
    db.flush()
    return db


def test_create_if_new_idempotent() -> None:
    db = _db()
    repo = EventRepository(db)
    captured = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    e1, created1 = repo.create_if_new(1, captured, "k", 1, 1.0, "c-1", event_id=10)
    e2, created2 = repo.create_if_new(1, captured, "k2", 1, 1.0, "c-2", event_id=11)
    assert created1 is True
    assert created2 is False
    assert e1.event_id == e2.event_id == 10


def test_alert_transition_conflict() -> None:
    db = _db()
    ev = Event(
        event_id=20,
        device_id=1,
        house_id=1,
        s3_key="k",
        captured_at=datetime(2026, 11, 1, 13, 0, tzinfo=UTC),
        correlation_id="c",
    )
    db.add(ev)
    db.flush()
    alerts = AlertRepository(db)
    alert = alerts.create_with_history_and_mark_event_scored(
        event_id=ev.event_id,
        house_id=1,
        room_id=1,
        device_id=1,
        alert_category="security",
        sound_type="glass_break",
        confidence=0.95,
        severity="high",
    )
    # SQLite needs explicit history/alert ids — set if missing
    if alert.alert_id is None:
        alert.alert_id = 1
        db.flush()
    alerts.transition(alert.alert_id, "new", "acknowledged", 1, "ok")
    with pytest.raises(StateConflictError) as exc:
        alerts.transition(alert.alert_id, "new", "resolved", 1, "stale")
    assert exc.value.details["current_state"] == "acknowledged"
