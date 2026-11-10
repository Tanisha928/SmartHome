"""PrefsRepository — full implementation."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.pg.models import NotificationPref
from app.persistence.repositories.base import BaseRepository


class PrefsRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_for_user_house(self, user_id: int, house_id: int) -> list[NotificationPref]:
        return list(
            self.db.scalars(
                select(NotificationPref).where(
                    NotificationPref.user_id == user_id,
                    NotificationPref.house_id == house_id,
                )
            ).all()
        )

    def upsert(
        self, user_id: int, house_id: int, prefs: list[dict[str, Any]]
    ) -> list[NotificationPref]:
        out: list[NotificationPref] = []
        for p in prefs:
            existing = self.db.scalars(
                select(NotificationPref).where(
                    NotificationPref.user_id == user_id,
                    NotificationPref.house_id == house_id,
                    NotificationPref.alert_category == p["alert_category"],
                )
            ).first()
            if existing:
                existing.email = bool(p.get("email", existing.email))
                existing.sms = bool(p.get("sms", existing.sms))
                existing.min_severity = p.get("min_severity", existing.min_severity)
                out.append(existing)
            else:
                row = NotificationPref(
                    user_id=user_id,
                    house_id=house_id,
                    alert_category=p["alert_category"],
                    email=bool(p.get("email", True)),
                    sms=bool(p.get("sms", False)),
                    min_severity=p.get("min_severity", "high"),
                )
                self.db.add(row)
                out.append(row)
        self.db.flush()
        return out
