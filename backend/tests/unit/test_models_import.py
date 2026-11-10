"""Models and metadata load for all PLAN 4.1 tables."""

from __future__ import annotations

from app.persistence.pg import models


EXPECTED_TABLES = {
    "users",
    "houses",
    "user_houses",
    "residents",
    "rooms",
    "devices",
    "device_commands",
    "events",
    "alerts",
    "alert_state_history",
    "alert_notifications",
    "notification_prefs",
    "admin_read_audit",
    "retention_policy",
    "threshold_overrides",
    "backup_status",
    "saved_views",
}


def test_all_tables_registered() -> None:
    names = set(models.Base.metadata.tables.keys())
    assert EXPECTED_TABLES.issubset(names)


def test_append_only_history_model_exists() -> None:
    assert hasattr(models, "AlertStateHistory")
    assert models.AlertStateHistory.__tablename__ == "alert_state_history"
