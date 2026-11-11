"""Repository for admin-managed alert threshold overrides."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.pg.models import ThresholdOverride


class ThresholdRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[ThresholdOverride]:
        return list(self.db.scalars(select(ThresholdOverride).order_by(ThresholdOverride.id)).all())

    def upsert(self, *, scope: str, scope_id: int | None, sound_type: str, threshold: float, user_id: int) -> ThresholdOverride:
        row = self.db.scalars(
            select(ThresholdOverride).where(
                ThresholdOverride.scope == scope,
                ThresholdOverride.scope_id == scope_id,
                ThresholdOverride.sound_type == sound_type,
            )
        ).first()
        if row is None:
            row = ThresholdOverride(
                scope=scope,
                scope_id=scope_id,
                sound_type=sound_type,
                threshold=threshold,
            )
            self.db.add(row)
        row.threshold = threshold
        row.updated_by = user_id
        row.updated_at = datetime.now(UTC)
        self.db.flush()
        return row

    def as_mappings(self) -> dict[str, dict[Any, float]]:
        result: dict[str, dict[Any, float]] = {"global": {}, "house": {}, "device": {}}
        for row in self.list():
            if row.scope == "global":
                result["global"][row.sound_type] = float(row.threshold)
            else:
                result[row.scope][(int(row.scope_id), row.sound_type)] = float(row.threshold)
        return result
