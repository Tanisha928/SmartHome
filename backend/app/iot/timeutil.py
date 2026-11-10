"""UTC helpers. SQLite (unit tests) returns naive datetimes, so normalize before comparing."""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def iso_z(value: datetime) -> str:
    return aware(value).astimezone(UTC).isoformat().replace("+00:00", "Z")
