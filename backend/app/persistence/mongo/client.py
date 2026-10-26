"""Mongo client + ensure_indexes for inference_logs and sensor_telemetry."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


@lru_cache
def get_mongo_client() -> MongoClient[Any]:
    settings = get_settings()
    return MongoClient(settings.mongo_url)


def get_db() -> Database[Any]:
    settings = get_settings()
    return get_mongo_client()[settings.mongo_db]


def inference_logs() -> Collection[Any]:
    return get_db()["inference_logs"]


def sensor_telemetry() -> Collection[Any]:
    return get_db()["sensor_telemetry"]


def ensure_indexes() -> None:
    """Create indexes per PLAN 4.2. Called at app startup."""
    settings = get_settings()
    logs = inference_logs()
    logs.create_index([("house_id", ASCENDING), ("created_at", DESCENDING)], name="ix_logs_house_created")
    logs.create_index([("event_id", ASCENDING)], unique=True, name="ix_logs_event_id")
    logs.create_index([("model.version", ASCENDING)], name="ix_logs_model_version")

    telem = sensor_telemetry()
    telem.create_index([("device_id", ASCENDING), ("ts", DESCENDING)], name="ix_telem_device_ts")
    # TTL on ts — expire after telemetry_ttl_days
    ttl_seconds = settings.telemetry_ttl_days * 24 * 60 * 60
    # Drop+recreate TTL if duration changes (idempotent best-effort)
    existing = {idx["name"]: idx for idx in telem.list_indexes()}
    ttl_name = "ix_telem_ts_ttl"
    if ttl_name in existing:
        prev = existing[ttl_name].get("expireAfterSeconds")
        if prev != ttl_seconds:
            telem.drop_index(ttl_name)
            telem.create_index([("ts", ASCENDING)], expireAfterSeconds=ttl_seconds, name=ttl_name)
    else:
        telem.create_index([("ts", ASCENDING)], expireAfterSeconds=ttl_seconds, name=ttl_name)

    log.info("mongo_indexes_ensured", ttl_seconds=ttl_seconds)
