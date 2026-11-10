"""RetentionRepository — full implementation with D1 validation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.persistence.pg.models import RetentionPolicy
from app.persistence.repositories.base import BaseRepository


class RetentionRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get(self) -> RetentionPolicy:
        policy = self.db.get(RetentionPolicy, 1)
        if policy is None:
            policy = RetentionPolicy(id=1, clip_expire_days=30, telemetry_ttl_days=30)
            self.db.add(policy)
            self.db.flush()
        return policy

    def put(self, **fields: Any) -> RetentionPolicy:
        policy = self.get()
        expire = fields.get("clip_expire_days", policy.clip_expire_days)
        ia = fields.get("clip_ia_transition_days", policy.clip_ia_transition_days)
        if ia is not None and expire is not None and ia >= expire:
            raise AppError(
                "IA transition days must be less than expire days",
                details={"error": "invalid_retention_range"},
            )
        if "clip_expire_days" in fields:
            policy.clip_expire_days = int(fields["clip_expire_days"])
        if "clip_ia_transition_days" in fields:
            policy.clip_ia_transition_days = fields["clip_ia_transition_days"]
        if "telemetry_ttl_days" in fields:
            policy.telemetry_ttl_days = int(fields["telemetry_ttl_days"])
        if "updated_by" in fields:
            policy.updated_by = fields["updated_by"]
        policy.updated_at = datetime.now(UTC)
        self.db.flush()
        return policy
