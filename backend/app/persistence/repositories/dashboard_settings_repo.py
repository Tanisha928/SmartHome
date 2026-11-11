"""Repository for per-user dashboard settings."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.pg.models import DashboardSettings
from app.persistence.repositories.base import BaseRepository


class DashboardSettingsRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_or_create(self, user_id: int) -> DashboardSettings:
        settings = self.db.scalar(select(DashboardSettings).where(DashboardSettings.user_id == user_id))
        if settings is None:
            settings = DashboardSettings(user_id=user_id)
            self.db.add(settings)
            self.db.flush()
        return settings

    def update(self, user_id: int, **fields: Any) -> DashboardSettings:
        settings = self.get_or_create(user_id)
        for key, value in fields.items():
            if value is not None:
                setattr(settings, key, value)
        self.db.flush()
        return settings

    @staticmethod
    def payload(settings: DashboardSettings) -> dict[str, Any]:
        return {
            "default_map_latitude": float(settings.default_map_latitude) if isinstance(settings.default_map_latitude, Decimal) else settings.default_map_latitude,
            "default_map_longitude": float(settings.default_map_longitude) if isinstance(settings.default_map_longitude, Decimal) else settings.default_map_longitude,
            "show_critical_toasts": settings.show_critical_toasts,
            "play_alert_sound": settings.play_alert_sound,
            "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
        }
