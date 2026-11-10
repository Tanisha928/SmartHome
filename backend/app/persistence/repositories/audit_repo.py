"""AuditRepository — full implementation."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.persistence.pg.models import AdminReadAudit
from app.persistence.repositories.base import BaseRepository


def _page(page: int, page_size: int) -> tuple[int, int]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    return page, page_size


class AuditRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def log_admin_read(self, **fields: Any) -> None:
        self.admin_read_audit(
            actor_user_id=fields["actor_user_id"],
            house_id=fields.get("house_id"),
            action=fields["action"],
            resource=fields.get("resource"),
            correlation_id=fields.get("correlation_id"),
        )

    def query(
        self,
        house: int | None,
        actor: int | None,
        type_: str | None,
        range_: Any,
        page: int,
        *,
        page_size: int = 25,
    ) -> dict[str, Any]:
        page, page_size = _page(page, page_size)
        stmt = select(AdminReadAudit)
        if house is not None:
            stmt = stmt.where(AdminReadAudit.house_id == house)
        if actor is not None:
            stmt = stmt.where(AdminReadAudit.actor_user_id == actor)
        if type_:
            stmt = stmt.where(AdminReadAudit.action == type_)
        if range_ and isinstance(range_, (list, tuple)) and len(range_) == 2:
            start, end = range_
            if start is not None:
                stmt = stmt.where(AdminReadAudit.ts >= start)
            if end is not None:
                stmt = stmt.where(AdminReadAudit.ts <= end)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            self.db.scalars(
                stmt.order_by(AdminReadAudit.ts.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return {"items": items, "total": total, "page": page, "page_size": page_size}
