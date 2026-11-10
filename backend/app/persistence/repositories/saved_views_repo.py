"""Saved views for admin live map filters."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.pg.models import SavedView
from app.persistence.repositories.base import BaseRepository


class SavedViewsRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_for_user(self, user_id: int) -> list[dict[str, Any]]:
        rows = self.db.scalars(select(SavedView).where(SavedView.user_id == user_id)).all()
        return [{"name": r.name, "filters": json.loads(r.filters_json)} for r in rows]

    def replace_for_user(self, user_id: int, views: list[dict[str, Any]]) -> list[dict[str, Any]]:
        existing = list(self.db.scalars(select(SavedView).where(SavedView.user_id == user_id)).all())
        for row in existing:
            self.db.delete(row)
        self.db.flush()
        for view in views:
            self.db.add(
                SavedView(
                    user_id=user_id,
                    name=str(view.get("name", "default")),
                    filters_json=json.dumps(view.get("filters", {})),
                )
            )
        self.db.flush()
        return self.get_for_user(user_id)
