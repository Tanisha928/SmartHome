"""Houses create/list with admin JWT and duplicate address 409."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.security import hash_password
from app.main import create_app
from app.persistence.pg.models import Base
from app.persistence.repositories.user_repo import UserRepository


@pytest.fixture
def house_client() -> Generator[tuple[TestClient, str], None, None]:
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

    # seed admin
    db = TestingSession()
    UserRepository(db).create(
        email="admin@example.com",
        password_hash=hash_password("admin-password-1"),
        full_name="Admin",
        role="admin",
    )
    db.commit()
    db.close()

    app = create_app()
    app.dependency_overrides[get_db] = _override
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "admin-password-1"},
        )
        token = login.json()["access_token"]
        yield client, token
    app.dependency_overrides.clear()


def test_create_and_list_house(house_client: tuple[TestClient, str]) -> None:
    client, token = house_client
    headers = {"Authorization": f"Bearer {token}"}
    with patch(
        "app.persistence.api.houses.create_house_sns_topic", return_value="arn:aws:sns:test"
    ):
        resp = client.post(
            "/api/houses",
            headers=headers,
            json={
                "address_line": "10 Test Way",
                "postal_code": "98101",
                "timezone": "America/Los_Angeles",
                "owner_email": "newowner@example.com",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["house_id"]
    assert body["sns_topic_arn"]
    assert body["owner"]["email"] == "newowner@example.com"

    listed = client.get("/api/houses", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    # duplicate
    with patch("app.persistence.api.houses.create_house_sns_topic", return_value=None):
        dup = client.post(
            "/api/houses",
            headers=headers,
            json={
                "address_line": "10 Test Way",
                "postal_code": "98101",
                "timezone": "America/Los_Angeles",
            },
        )
    assert dup.status_code == 409
