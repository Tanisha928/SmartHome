"""BaseRepository.apply_scope — tenant isolation + admin_read_audit."""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, Select
from sqlalchemy.orm import Session

from app.core.deps import Claims
from app.core.logging import get_logger
from app.persistence.pg.models import AdminReadAudit

log = get_logger(__name__)


class BaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def apply_scope(
        self,
        stmt: Select[Any],
        claims: Claims,
        house_col: ColumnElement[Any],
        *,
        action: str = "read",
        resource: str | None = None,
        correlation_id: str | None = None,
    ) -> Select[Any]:
        """Admin: no filter, write admin_read_audit. Owner: filter house_ids (empty → no rows)."""
        if claims.type == "user" and claims.role == "admin":
            self.admin_read_audit(
                actor_user_id=claims.user_id,
                house_id=None,
                action=action,
                resource=resource,
                correlation_id=correlation_id,
            )
            return stmt

        house_ids = list(claims.house_ids) if claims.type == "user" else []
        if claims.type == "device" and claims.house_id is not None:
            house_ids = [claims.house_id]

        if not house_ids:
            return stmt.where(house_col.in_([]))  # empty IN → no rows
        return stmt.where(house_col.in_(house_ids))

    def admin_read_audit(
        self,
        *,
        actor_user_id: int,
        house_id: int | None,
        action: str,
        resource: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        self.db.add(
            AdminReadAudit(
                actor_user_id=actor_user_id,
                house_id=house_id,
                action=action,
                resource=resource,
                correlation_id=correlation_id,
            )
        )
