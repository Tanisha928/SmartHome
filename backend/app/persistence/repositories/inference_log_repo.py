"""InferenceLogRepository (MongoDB) skeleton."""

from __future__ import annotations

from typing import Any


class InferenceLogRepository:
    def write(self, doc: dict[str, Any]) -> str:
        raise NotImplementedError

    def query(self, filters: dict[str, Any], page: int, *, page_size: int = 25) -> dict[str, Any]:
        raise NotImplementedError
