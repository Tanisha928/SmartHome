from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.alerts import api as alert_api
from app.core.deps import Claims, get_db, require_user
from app.core.errors import ForbiddenError, StateConflictError
from app.main import create_app


ALERT = SimpleNamespace(
    alert_id=7,
    event_id=8,
    house_id=1,
    room_id=2,
    device_id=3,
    alert_category="security",
    sound_type="glass_break",
    confidence=0.95,
    severity="high",
    state="acknowledged",
    suppressed_count=0,
    version=2,
    created_at=None,
    updated_at=None,
)


class FakeAlertRepository:
    def list(self, filters: dict[str, object], _page: int, claims: Claims, **_kwargs: object) -> dict[str, object]:
        requested_house = filters.get("house_id")
        if claims.role != "admin" and requested_house is not None and requested_house not in claims.house_ids:
            raise ForbiddenError("House out of scope")
        return {"items": [ALERT], "total": 1, "page": 1, "page_size": 100}

    def get_detail_bundle(self, _alert_id: int, claims: Claims) -> dict[str, object]:
        if claims.role != "admin" and ALERT.house_id not in claims.house_ids:
            raise ForbiddenError("Alert out of scope")
        return {"alert": ALERT, "history": [], "deliveries": []}

    def get_detail(self, _alert_id: int, claims: Claims) -> SimpleNamespace:
        if claims.role != "admin" and ALERT.house_id not in claims.house_ids:
            raise ForbiddenError("Alert out of scope")
        return ALERT

    def stats(self, **_filters: object) -> dict[str, object]:
        return {"total": 1, "by_severity": {"high": 1}, "by_category": {"security": 1}, "by_state": {"acknowledged": 1}}

    def false_alert_stats(self, **_filters: object) -> list[object]:
        return []

    def transition(self, *_args: object) -> None:
        raise StateConflictError("Alert state conflict")


class FakePrefs:
    def get_for_user_house(self, *_args: object) -> list[object]:
        return []

    def upsert(self, *_args: object) -> list[object]:
        return []


@pytest.fixture
def alert_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = create_app()
    claims = Claims(sub=10, type="user", role="owner", house_ids=[1])
    app.dependency_overrides[require_user] = lambda: claims
    app.dependency_overrides[get_db] = lambda: object()
    monkeypatch.setattr(alert_api, "AlertRepository", FakeAlertRepository)
    monkeypatch.setattr(alert_api, "PrefsRepository", FakePrefs)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "path",
    [
        "/api/alerts?house_id=1",
        "/api/alerts/export?house_id=1",
        "/api/stats/alerts?house_id=1",
        "/api/stats/false-alerts?house_id=1",
        "/api/notification-prefs?house_id=1",
        "/api/alerts/7",
    ],
)
def test_scoped_alert_reads_allow_owned_house(alert_client: TestClient, path: str) -> None:
    assert alert_client.get(path).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/alerts?house_id=2",
        "/api/alerts/export?house_id=2",
        "/api/stats/alerts?house_id=2",
        "/api/stats/false-alerts?house_id=2",
        "/api/notification-prefs?house_id=2",
    ],
)
def test_scoped_alert_reads_reject_other_house(alert_client: TestClient, path: str) -> None:
    assert alert_client.get(path).status_code == 403


def test_state_conflict_is_returned_as_http_409(alert_client: TestClient) -> None:
    response = alert_client.patch(
        "/api/alerts/7/state",
        json={"to_state": "resolved", "expected_state": "acknowledged"},
    )
    assert response.status_code == 409
    assert response.json()["error"] == "state_conflict"
