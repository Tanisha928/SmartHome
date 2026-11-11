"""SQLAlchemy models — PLAN.md section 4.1 (13 tables + proposed additions)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    must_reset: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (CheckConstraint("role IN ('owner','admin')", name="ck_users_role"),)

    houses: Mapped[list[UserHouse]] = relationship(back_populates="user")


class House(Base):
    __tablename__ = "houses"

    house_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    address_line: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(50))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("status IN ('active','disabled')", name="ck_houses_status"),
        UniqueConstraint("address_line", "postal_code", name="uq_houses_address_postal"),
    )

    rooms: Mapped[list[Room]] = relationship(back_populates="house")
    devices: Mapped[list[Device]] = relationship(back_populates="house")
    users: Mapped[list[UserHouse]] = relationship(back_populates="house")


class UserHouse(Base):
    __tablename__ = "user_houses"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.house_id"), nullable=False)
    relation: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "house_id"),
        CheckConstraint(
            "relation IN ('owner','family','caregiver')", name="ck_user_houses_relation"
        ),
        Index("ix_user_houses_user_house", "user_id", "house_id"),
    )

    user: Mapped[User] = relationship(back_populates="houses")
    house: Mapped[House] = relationship(back_populates="users")


class Resident(Base):
    __tablename__ = "residents"

    resident_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.house_id"), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    birth_year: Mapped[int | None] = mapped_column(Integer)
    care_notes: Mapped[str | None] = mapped_column(Text)


class Room(Base):
    __tablename__ = "rooms"

    room_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.house_id"), nullable=False)
    room_type: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "room_type IN ('kitchen','living','bedroom','bath','other')",
            name="ck_rooms_type",
        ),
        UniqueConstraint("house_id", "label", name="uq_rooms_house_label"),
    )

    house: Mapped[House] = relationship(back_populates="rooms")
    devices: Mapped[list[Device]] = relationship(back_populates="room")


class Device(Base):
    __tablename__ = "devices"

    device_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.room_id"), nullable=False)
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.house_id"), nullable=False)
    device_type: Mapped[str] = mapped_column(String(20), nullable=False)
    serial_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'enabled'")
    )
    conn_state: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'offline'")
    )
    wifi_rssi: Mapped[int | None] = mapped_column(Integer)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    api_key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_prefix: Mapped[str | None] = mapped_column(String(20))
    key_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("device_type IN ('audio','camera')", name="ck_devices_type"),
        CheckConstraint("status IN ('enabled','disabled')", name="ck_devices_status"),
        CheckConstraint("conn_state IN ('online','offline')", name="ck_devices_conn"),
        CheckConstraint(
            "threshold IS NULL OR (threshold BETWEEN 0.50 AND 0.99)",
            name="ck_devices_threshold",
        ),
        Index("ix_devices_house_conn", "house_id", "conn_state"),
        Index("ix_devices_last_heartbeat", "last_heartbeat"),
    )

    house: Mapped[House] = relationship(back_populates="devices")
    room: Mapped[Room] = relationship(back_populates="devices")


class DeviceCommand(Base):
    __tablename__ = "device_commands"

    command_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.device_id"), nullable=False)
    command: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    issued_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("command IN ('enable','disable','reboot')", name="ck_commands_cmd"),
        CheckConstraint(
            "status IN ('pending','delivered','completed','failed','expired')",
            name="ck_commands_status",
        ),
        Index("ix_device_commands_device_status", "device_id", "status"),
    )


class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.device_id"), nullable=False)
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.house_id"), nullable=False)
    s3_key: Mapped[str | None] = mapped_column(String(500))
    duration_sec: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processing_state: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'queued'")
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    decision: Mapped[str | None] = mapped_column(String(40))

    __table_args__ = (
        CheckConstraint("processing_state IN ('queued','scored','failed')", name="ck_events_state"),
        UniqueConstraint("device_id", "captured_at", name="uq_events_device_captured"),
        Index("ix_events_state_received", "processing_state", "received_at"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    alert_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.event_id"), unique=True, nullable=False
    )
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.house_id"), nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.room_id"), nullable=False)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.device_id"), nullable=False)
    resident_id: Mapped[int | None] = mapped_column(ForeignKey("residents.resident_id"))
    alert_category: Mapped[str] = mapped_column(String(20), nullable=False)
    sound_type: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'new'"))
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    suppressed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "alert_category IN ('emergency','safety','security','resident','animal')",
            name="ck_alerts_category",
        ),
        CheckConstraint(
            "severity IN ('critical','high','medium','low')", name="ck_alerts_severity"
        ),
        CheckConstraint(
            "state IN ('new','notified','acknowledged','escalated','resolved','false_positive')",
            name="ck_alerts_state",
        ),
        Index("ix_alerts_house_created", "house_id", "created_at"),
        Index("ix_alerts_state_severity", "state", "severity"),
        Index("ix_alerts_house_category_created", "house_id", "alert_category", "created_at"),
    )


class AlertStateHistory(Base):
    __tablename__ = "alert_state_history"

    history_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.alert_id"), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(20))
    to_state: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    note: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_alert_history_alert_changed", "alert_id", "changed_at"),)


class AlertNotification(Base):
    __tablename__ = "alert_notifications"

    notification_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.alert_id"), nullable=False)
    recipient_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    recipient_label: Mapped[str | None] = mapped_column(String(200))
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("channel IN ('email','sms')", name="ck_notif_channel"),
        CheckConstraint("status IN ('pending','sent','failed')", name="ck_notif_status"),
        UniqueConstraint(
            "alert_id", "recipient_id", "channel", name="uq_notif_alert_recipient_channel"
        ),
    )


class NotificationPref(Base):
    __tablename__ = "notification_prefs"

    pref_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.house_id"), nullable=False)
    alert_category: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sms: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    min_severity: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "min_severity IN ('critical','high','medium','low')", name="ck_prefs_severity"
        ),
        UniqueConstraint(
            "user_id", "house_id", "alert_category", name="uq_prefs_user_house_category"
        ),
    )


class AdminReadAudit(Base):
    __tablename__ = "admin_read_audit"

    audit_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    house_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource: Mapped[str | None] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64))


class RetentionPolicy(Base):
    __tablename__ = "retention_policy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clip_expire_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("30")
    )
    clip_ia_transition_days: Mapped[int | None] = mapped_column(Integer)
    telemetry_ttl_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("30")
    )
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ThresholdOverride(Base):
    __tablename__ = "threshold_overrides"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_id: Mapped[int | None] = mapped_column(BigInteger)
    sound_type: Mapped[str] = mapped_column(String(64), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("scope IN ('global','house','device')", name="ck_threshold_scope"),
        UniqueConstraint("scope", "scope_id", "sound_type", name="uq_threshold_scope"),
    )


class BackupStatus(Base):
    __tablename__ = "backup_status"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str | None] = mapped_column(String(40))
    location: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("kind IN ('rds_snapshot','mongo_dump')", name="ck_backup_kind"),
    )


class SavedView(Base):
    """Admin saved filter views for A2 live map (PLAN 7.2)."""

    __tablename__ = "saved_views"

    view_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    filters_json: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'{}'"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_saved_views_user_name"),)


class DashboardSettings(Base):
    """Per-user dashboard preferences used by the Mithil dashboard."""

    __tablename__ = "dashboard_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    default_map_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    default_map_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    show_critical_toasts: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    play_alert_sound: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
