"""Auth signup/login/refresh/logout and rate-limit behavior."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.ratelimit import login_limiter
from app.main import create_app
from app.persistence.pg.models import Base


@pytest.fixture
def auth_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("ENV", "test")
    from app.core.config import get_settings

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

    app = create_app()
    app.dependency_overrides[get_db] = _override
    login_limiter.clear()
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    login_limiter.clear()
    get_settings.cache_clear()


def test_signup_login_refresh_logout(auth_client: TestClient) -> None:
    resp = auth_client.post(
        "/api/auth/signup",
        json={
            "email": "owner@example.com",
            "password": "password1234",
            "full_name": "Owner One",
            "phone": "+15551112222",
        },
    )
    assert resp.status_code == 201

    login = auth_client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "password1234"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["user"]["role"] == "owner"
    assert "access_token" in body
    assert "rt" in login.cookies

    me = auth_client.get(
        "/api/users/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "owner@example.com"

    refreshed = auth_client.post("/api/auth/refresh")
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()

    out = auth_client.post("/api/auth/logout")
    assert out.status_code == 204


def test_duplicate_signup_409(auth_client: TestClient) -> None:
    payload = {
        "email": "dup@example.com",
        "password": "password1234",
        "full_name": "Dup",
    }
    assert auth_client.post("/api/auth/signup", json=payload).status_code == 201
    resp = auth_client.post("/api/auth/signup", json=payload)
    assert resp.status_code == 409


def test_login_rate_limit_429(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/auth/signup",
        json={"email": "rl@example.com", "password": "password1234", "full_name": "RL"},
    )
    for _ in range(5):
        auth_client.post(
            "/api/auth/login", json={"email": "rl@example.com", "password": "wrong-password"}
        )
    resp = auth_client.post(
        "/api/auth/login", json={"email": "rl@example.com", "password": "wrong-password"}
    )
    assert resp.status_code == 429
