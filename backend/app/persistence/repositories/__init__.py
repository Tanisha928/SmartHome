"""Repository layer — PLAN 4.4 signatures. Only persistence touches DBs/AWS."""

from app.persistence.repositories.alert_repo import AlertRepository
from app.persistence.repositories.audit_repo import AuditRepository
from app.persistence.repositories.base import BaseRepository
from app.persistence.repositories.command_repo import CommandRepository
from app.persistence.repositories.device_repo import DeviceRepository
from app.persistence.repositories.event_repo import EventRepository
from app.persistence.repositories.house_repo import HouseRepository
from app.persistence.repositories.inference_log_repo import InferenceLogRepository
from app.persistence.repositories.notification_repo import NotificationRepository
from app.persistence.repositories.prefs_repo import PrefsRepository
from app.persistence.repositories.retention_repo import RetentionRepository
from app.persistence.repositories.room_repo import RoomRepository
from app.persistence.repositories.saved_views_repo import SavedViewsRepository
from app.persistence.repositories.telemetry_repo import TelemetryRepository
from app.persistence.repositories.user_repo import UserRepository

__all__ = [
    "AlertRepository",
    "AuditRepository",
    "BaseRepository",
    "CommandRepository",
    "DeviceRepository",
    "EventRepository",
    "HouseRepository",
    "InferenceLogRepository",
    "NotificationRepository",
    "PrefsRepository",
    "RetentionRepository",
    "RoomRepository",
    "SavedViewsRepository",
    "TelemetryRepository",
    "UserRepository",
]
