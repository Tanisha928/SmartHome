"""apply_scope filters owner house_ids; admin records audit."""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import Claims
from app.persistence.pg.models import Base, House
from app.persistence.repositories.base import BaseRepository


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Only tables needed for scope filter statements
    House.__table__.create(engine, checkfirst=True)
    return sessionmaker(bind=engine)()


def test_owner_cannot_see_other_house() -> None:
    db = _session()
    h1 = House(house_id=1, timezone="America/Los_Angeles", address_line="a", postal_code="1")
    h2 = House(house_id=2, timezone="America/Los_Angeles", address_line="b", postal_code="2")
    db.add_all([h1, h2])
    db.flush()

    repo = BaseRepository(db)
    claims = Claims(sub=10, type="user", role="owner", house_ids=[1])
    stmt = repo.apply_scope(select(House), claims, House.house_id)
    ids = list(db.scalars(stmt).all())
    assert [h.house_id for h in ids] == [1]


def test_admin_read_writes_audit() -> None:
    db = MagicMock()
    repo = BaseRepository(db)
    repo.admin_read_audit = MagicMock()  # type: ignore[method-assign]
    claims = Claims(sub=1, type="user", role="admin", house_ids=[])
    stmt = select(House)
    out = repo.apply_scope(stmt, claims, House.house_id, action="list_houses", resource="houses")
    assert out is stmt
    repo.admin_read_audit.assert_called_once()
    kwargs = repo.admin_read_audit.call_args.kwargs
    assert kwargs["actor_user_id"] == 1
    assert kwargs["action"] == "list_houses"


def test_empty_house_ids_returns_no_rows() -> None:
    db = _session()
    db.add(House(house_id=1, timezone="UTC", address_line="a", postal_code="1"))
    db.flush()
    repo = BaseRepository(db)
    claims = Claims(sub=2, type="user", role="owner", house_ids=[])
    stmt = repo.apply_scope(select(House), claims, House.house_id)
    assert list(db.scalars(stmt).all()) == []
