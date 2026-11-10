"""Correlation-id middleware echoes or generates X-Correlation-Id."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_correlation_id_generated(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert "X-Correlation-Id" in resp.headers
    assert resp.headers["X-Correlation-Id"].startswith("c-")


def test_correlation_id_echoed(client: TestClient) -> None:
    resp = client.get("/healthz", headers={"X-Correlation-Id": "c-test1234567890"})
    assert resp.headers["X-Correlation-Id"] == "c-test1234567890"
