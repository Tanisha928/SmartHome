"""Shared fixtures for IoT Device Manager tests: in-memory SQLite, seeded houses, tokens."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.deps import get_db
from app.core.ratelimit import device_token_limiter
from app.core.security import create_access_token, hash_password
from app.iot import events
from app.main import create_app
from app.persistence.pg.models import Base, House, Room, User, UserHouse
from app.persistence.repositories.telemetry_repo import TelemetryRepository


@dataclass
class IotEnv:
    client: TestClient
    Session: sessionmaker[Session]
    admin: dict[str, str]
    owner_a: dict[str, str]
    owner_b: dict[str, str]
    house_a: int
    house_b: int
    room_a: int
    room_b: int
    published: list[dict[str, Any]] = field(default_factory=list)
    telemetry: list[dict[str, Any]] = field(default_factory=list)

    def register(self, headers: dict[str, str], *, room_id: int, serial: str) -> dict[str, Any]:
        resp = self.client.post(
            "/api/devices",
            headers=headers,
            json={"room_id": room_id, "device_type": "audio", "serial_no": serial, "label": serial},
        )
        assert resp.status_code == 201, resp.text
        return dict(resp.json())

    def device_headers(self, device_id: int, api_key: str) -> dict[str, str]:
        resp = self.client.post(
            "/api/auth/device-token", json={"device_id": device_id, "api_key": api_key}
        )
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    def heartbeat(self, device_id: int, headers: dict[str, str], *, config_version: int = 0) -> Any:
        return self.client.post(
            f"/api/devices/{device_id}/heartbeat",
            headers=headers,
            json={
                "wifi_rssi": -55,
                "uptime_sec": 10,
                "buffer_depth": 0,
                "config_version": config_version,
            },
        )


def _bearer(user_id: int, role: str, house_ids: list[int]) -> dict[str, str]:
    token, _ = create_access_token(subject=user_id, role=role, house_ids=house_ids)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def iot(monkeypatch: pytest.MonkeyPatch) -> Generator[IotEnv, None, None]:
    monkeypatch.setenv("ENV", "test")  # skip Mongo index creation at startup
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def _override() -> Generator[Session, None, None]:
        db = TestingSession()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    db = TestingSession()
    pw = hash_password("password-123456")
    admin = User(email="admin@x.io", password_hash=pw, role="admin", full_name="Admin")
    oa = User(email="a@x.io", password_hash=pw, role="owner", full_name="Owner A")
    ob = User(email="b@x.io", password_hash=pw, role="owner", full_name="Owner B")
    ha = House(address_line="1 A St", postal_code="11111", timezone="UTC")
    hb = House(address_line="2 B St", postal_code="22222", timezone="UTC")
    db.add_all([admin, oa, ob, ha, hb])
    db.flush()
    db.add_all(
        [
            UserHouse(user_id=oa.user_id, house_id=ha.house_id, relation="owner"),
            UserHouse(user_id=ob.user_id, house_id=hb.house_id, relation="owner"),
        ]
    )
    ra = Room(house_id=ha.house_id, room_type="living", label="Living")
    rb = Room(house_id=hb.house_id, room_type="kitchen", label="Kitchen")
    db.add_all([ra, rb])
    db.commit()

    published: list[dict[str, Any]] = []
    telemetry: list[dict[str, Any]] = []
    events.set_sink(published.append)

    def _fake_write(_self: Any, **fields: Any) -> str:
        telemetry.append(fields)
        return "t-1"

    monkeypatch.setattr(TelemetryRepository, "write_heartbeat", _fake_write)
    device_token_limiter.clear()

    app = create_app()
    app.dependency_overrides[get_db] = _override
    with TestClient(app) as client:
        yield IotEnv(
            client=client,
            Session=TestingSession,
            admin=_bearer(admin.user_id, "admin", []),
            owner_a=_bearer(oa.user_id, "owner", [ha.house_id]),
            owner_b=_bearer(ob.user_id, "owner", [hb.house_id]),
            house_a=ha.house_id,
            house_b=hb.house_id,
            room_a=ra.room_id,
            room_b=rb.room_id,
            published=published,
            telemetry=telemetry,
        )
    db.close()
    events.set_sink(None)
    app.dependency_overrides.clear()
    get_settings.cache_clear()
