"""Initial schema: 13 core tables + proposed additions + append-only trigger.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-22 11:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("must_reset", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('owner','admin')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "houses",
        sa.Column("house_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("address_line", sa.String(length=300), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=50), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_houses_status"),
        sa.PrimaryKeyConstraint("house_id"),
        sa.UniqueConstraint("address_line", "postal_code", name="uq_houses_address_postal"),
    )

    op.create_table(
        "user_houses",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("house_id", sa.BigInteger(), nullable=False),
        sa.Column("relation", sa.String(length=20), nullable=False),
        sa.CheckConstraint("relation IN ('owner','family','caregiver')", name="ck_user_houses_relation"),
        sa.ForeignKeyConstraint(["house_id"], ["houses.house_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("user_id", "house_id"),
    )
    op.create_index("ix_user_houses_user_house", "user_houses", ["user_id", "house_id"])

    op.create_table(
        "residents",
        sa.Column("resident_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("house_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("birth_year", sa.Integer(), nullable=True),
        sa.Column("care_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["house_id"], ["houses.house_id"]),
        sa.PrimaryKeyConstraint("resident_id"),
    )

    op.create_table(
        "rooms",
        sa.Column("room_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("house_id", sa.BigInteger(), nullable=False),
        sa.Column("room_type", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.CheckConstraint(
            "room_type IN ('kitchen','living','bedroom','bath','other')", name="ck_rooms_type"
        ),
        sa.ForeignKeyConstraint(["house_id"], ["houses.house_id"]),
        sa.PrimaryKeyConstraint("room_id"),
        sa.UniqueConstraint("house_id", "label", name="uq_rooms_house_label"),
    )

    op.create_table(
        "devices",
        sa.Column("device_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.BigInteger(), nullable=False),
        sa.Column("house_id", sa.BigInteger(), nullable=False),
        sa.Column("device_type", sa.String(length=20), nullable=False),
        sa.Column("serial_no", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'enabled'"), nullable=False),
        sa.Column("conn_state", sa.String(length=20), server_default=sa.text("'offline'"), nullable=False),
        sa.Column("wifi_rssi", sa.Integer(), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("threshold", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("api_key_hash", sa.Text(), nullable=False),
        sa.Column("api_key_prefix", sa.String(length=20), nullable=True),
        sa.Column("key_revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("device_type IN ('audio','camera')", name="ck_devices_type"),
        sa.CheckConstraint("status IN ('enabled','disabled')", name="ck_devices_status"),
        sa.CheckConstraint("conn_state IN ('online','offline')", name="ck_devices_conn"),
        sa.CheckConstraint(
            "threshold IS NULL OR (threshold BETWEEN 0.50 AND 0.99)",
            name="ck_devices_threshold",
        ),
        sa.ForeignKeyConstraint(["house_id"], ["houses.house_id"]),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.room_id"]),
        sa.PrimaryKeyConstraint("device_id"),
        sa.UniqueConstraint("serial_no"),
    )
    op.create_index("ix_devices_house_conn", "devices", ["house_id", "conn_state"])
    op.create_index("ix_devices_last_heartbeat", "devices", ["last_heartbeat"])

    op.create_table(
        "device_commands",
        sa.Column("command_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.BigInteger(), nullable=False),
        sa.Column("command", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("issued_by", sa.BigInteger(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.CheckConstraint("command IN ('enable','disable','reboot')", name="ck_commands_cmd"),
        sa.CheckConstraint(
            "status IN ('pending','delivered','completed','failed','expired')",
            name="ck_commands_status",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(["issued_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("command_id"),
    )
    op.create_index("ix_device_commands_device_status", "device_commands", ["device_id", "status"])

    op.create_table(
        "events",
        sa.Column("event_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.BigInteger(), nullable=False),
        sa.Column("house_id", sa.BigInteger(), nullable=False),
        sa.Column("s3_key", sa.String(length=500), nullable=True),
        sa.Column("duration_sec", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "processing_state",
            sa.String(length=20),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("decision", sa.String(length=40), nullable=True),
        sa.CheckConstraint(
            "processing_state IN ('queued','scored','failed')", name="ck_events_state"
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(["house_id"], ["houses.house_id"]),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("device_id", "captured_at", name="uq_events_device_captured"),
    )
    op.create_index("ix_events_state_received", "events", ["processing_state", "received_at"])

    op.create_table(
        "alerts",
        sa.Column("alert_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("house_id", sa.BigInteger(), nullable=False),
        sa.Column("room_id", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.BigInteger(), nullable=False),
        sa.Column("resident_id", sa.BigInteger(), nullable=True),
        sa.Column("alert_category", sa.String(length=20), nullable=False),
        sa.Column("sound_type", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("state", sa.String(length=20), server_default=sa.text("'new'"), nullable=False),
        sa.Column("resolved_by", sa.BigInteger(), nullable=True),
        sa.Column("suppressed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "alert_category IN ('emergency','safety','security','resident','animal')",
            name="ck_alerts_category",
        ),
        sa.CheckConstraint(
            "severity IN ('critical','high','medium','low')", name="ck_alerts_severity"
        ),
        sa.CheckConstraint(
            "state IN ('new','notified','acknowledged','escalated','resolved','false_positive')",
            name="ck_alerts_state",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(["event_id"], ["events.event_id"]),
        sa.ForeignKeyConstraint(["house_id"], ["houses.house_id"]),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.resident_id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.room_id"]),
        sa.PrimaryKeyConstraint("alert_id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_alerts_house_created", "alerts", ["house_id", "created_at"])
    op.create_index("ix_alerts_state_severity", "alerts", ["state", "severity"])
    op.create_index(
        "ix_alerts_house_category_created", "alerts", ["house_id", "alert_category", "created_at"]
    )

    op.create_table(
        "alert_state_history",
        sa.Column("history_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("alert_id", sa.BigInteger(), nullable=False),
        sa.Column("from_state", sa.String(length=20), nullable=True),
        sa.Column("to_state", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.alert_id"]),
        sa.PrimaryKeyConstraint("history_id"),
    )
    op.create_index(
        "ix_alert_history_alert_changed", "alert_state_history", ["alert_id", "changed_at"]
    )

    # Append-only: raise on UPDATE/DELETE
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_alert_history_mutation()
        RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'alert_state_history is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_alert_state_history_append_only
        BEFORE UPDATE OR DELETE ON alert_state_history
        FOR EACH ROW EXECUTE PROCEDURE prevent_alert_history_mutation();
        """
    )

    op.create_table(
        "alert_notifications",
        sa.Column("notification_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("alert_id", sa.BigInteger(), nullable=False),
        sa.Column("recipient_id", sa.BigInteger(), nullable=True),
        sa.Column("recipient_label", sa.String(length=200), nullable=True),
        sa.Column("channel", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("channel IN ('email','sms')", name="ck_notif_channel"),
        sa.CheckConstraint("status IN ('pending','sent','failed')", name="ck_notif_status"),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.alert_id"]),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("notification_id"),
        sa.UniqueConstraint(
            "alert_id", "recipient_id", "channel", name="uq_notif_alert_recipient_channel"
        ),
    )

    op.create_table(
        "notification_prefs",
        sa.Column("pref_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("house_id", sa.BigInteger(), nullable=False),
        sa.Column("alert_category", sa.String(length=20), nullable=False),
        sa.Column("email", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sms", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("min_severity", sa.String(length=20), nullable=False),
        sa.CheckConstraint(
            "min_severity IN ('critical','high','medium','low')", name="ck_prefs_severity"
        ),
        sa.ForeignKeyConstraint(["house_id"], ["houses.house_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("pref_id"),
        sa.UniqueConstraint(
            "user_id", "house_id", "alert_category", name="uq_prefs_user_house_category"
        ),
    )

    op.create_table(
        "admin_read_audit",
        sa.Column("audit_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("house_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource", sa.Text(), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("audit_id"),
    )

    op.create_table(
        "retention_policy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clip_expire_days", sa.Integer(), server_default=sa.text("30"), nullable=False),
        sa.Column("clip_ia_transition_days", sa.Integer(), nullable=True),
        sa.Column("telemetry_ttl_days", sa.Integer(), server_default=sa.text("30"), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "INSERT INTO retention_policy (id, clip_expire_days, telemetry_ttl_days) VALUES (1, 30, 30)"
    )

    op.create_table(
        "threshold_overrides",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("scope_id", sa.BigInteger(), nullable=True),
        sa.Column("sound_type", sa.String(length=64), nullable=False),
        sa.Column("threshold", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("scope IN ('global','house','device')", name="ck_threshold_scope"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "scope_id", "sound_type", name="uq_threshold_scope"),
    )

    op.create_table(
        "backup_status",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.CheckConstraint("kind IN ('rds_snapshot','mongo_dump')", name="ck_backup_kind"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "saved_views",
        sa.Column("view_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("filters_json", sa.Text(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("view_id"),
        sa.UniqueConstraint("user_id", "name", name="uq_saved_views_user_name"),
    )


def downgrade() -> None:
    op.drop_table("saved_views")
    op.drop_table("backup_status")
    op.drop_table("threshold_overrides")
    op.drop_table("retention_policy")
    op.drop_table("admin_read_audit")
    op.drop_table("notification_prefs")
    op.drop_table("alert_notifications")
    op.execute("DROP TRIGGER IF EXISTS trg_alert_state_history_append_only ON alert_state_history")
    op.execute("DROP FUNCTION IF EXISTS prevent_alert_history_mutation()")
    op.drop_index("ix_alert_history_alert_changed", table_name="alert_state_history")
    op.drop_table("alert_state_history")
    op.drop_index("ix_alerts_house_category_created", table_name="alerts")
    op.drop_index("ix_alerts_state_severity", table_name="alerts")
    op.drop_index("ix_alerts_house_created", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_events_state_received", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_device_commands_device_status", table_name="device_commands")
    op.drop_table("device_commands")
    op.drop_index("ix_devices_last_heartbeat", table_name="devices")
    op.drop_index("ix_devices_house_conn", table_name="devices")
    op.drop_table("devices")
    op.drop_table("rooms")
    op.drop_table("residents")
    op.drop_index("ix_user_houses_user_house", table_name="user_houses")
    op.drop_table("user_houses")
    op.drop_table("houses")
    op.drop_table("users")
