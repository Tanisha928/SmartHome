"""ensure_indexes is callable with a monkeypatched client (no live Mongo required)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from app.persistence.mongo import client as mongo_client


def test_ensure_indexes_creates_expected(monkeypatch: Any) -> None:
    logs = MagicMock()
    telem = MagicMock()
    telem.list_indexes.return_value = []
    db = {"inference_logs": logs, "sensor_telemetry": telem}

    monkeypatch.setattr(mongo_client, "get_db", lambda: db)
    mongo_client.ensure_indexes()

    assert logs.create_index.call_count >= 3
    assert telem.create_index.call_count >= 2
