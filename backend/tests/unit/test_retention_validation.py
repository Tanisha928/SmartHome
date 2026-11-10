"""Retention D1 validation: ia_transition_days < expire_days."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import AppError
from app.persistence.pg.models import Base, RetentionPolicy
from app.persistence.repositories.retention_repo import RetentionRepository


def test_invalid_ia_range() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(RetentionPolicy(id=1, clip_expire_days=30, telemetry_ttl_days=30))
    db.flush()
    repo = RetentionRepository(db)
    with pytest.raises(AppError) as exc:
        repo.put(clip_expire_days=30, clip_ia_transition_days=30)
    assert exc.value.details["error"] == "invalid_retention_range"
