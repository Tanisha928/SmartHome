"""InferenceLogRepository (MongoDB) — full implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.persistence.mongo.client import inference_logs


class InferenceLogRepository:
    def write(self, doc: dict[str, Any]) -> str:
        payload = dict(doc)
        payload.setdefault("created_at", datetime.now(UTC))
        result = inference_logs().insert_one(payload)
        return str(result.inserted_id)

    def query(self, filters: dict[str, Any], page: int, *, page_size: int = 25) -> dict[str, Any]:
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        query: dict[str, Any] = {}
        if filters.get("house_id") is not None:
            query["house_id"] = filters["house_id"]
        if filters.get("event_id") is not None:
            query["event_id"] = filters["event_id"]
        if filters.get("model_version") is not None:
            query["model.version"] = filters["model_version"]
        if filters.get("label") is not None:
            query["predictions.label"] = filters["label"]
        coll = inference_logs()
        total = coll.count_documents(query)
        cursor = (
            coll.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        items = []
        for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            items.append(doc)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def get(self, log_id: str) -> dict[str, Any] | None:
        doc = inference_logs().find_one({"_id": ObjectId(log_id)})
        if not doc:
            return None
        doc["id"] = str(doc.pop("_id"))
        return doc
