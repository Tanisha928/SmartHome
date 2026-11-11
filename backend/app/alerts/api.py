"""MVP alert endpoints for listing, inspection, and state transitions."""

from __future__ import annotations

from datetime import datetime
from io import StringIO
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.alerts.alert_state_service import AlertStateService
from app.alerts.notification_dispatcher import NotificationDispatcher
from app.alerts.policy_engine import PolicyEngine
from app.alerts.threshold_resolver import ThresholdResolver
from app.core.config import get_settings
from app.core.deps import Claims, get_db, require_user
from app.core.errors import DependencyUnavailableError, ForbiddenError, UnprocessableError
from app.persistence.repositories.alert_repo import AlertRepository
from app.persistence.repositories.device_repo import DeviceRepository
from app.persistence.repositories.event_repo import EventRepository
from app.persistence.repositories.inference_log_repo import InferenceLogRepository
from app.persistence.repositories.notification_repo import NotificationRepository
from app.persistence.repositories.prefs_repo import PrefsRepository
from app.persistence.repositories.threshold_repo import ThresholdRepository

router = APIRouter(tags=["alerts"])


class AlertStateUpdate(BaseModel):
    to_state: Literal[
        "notified",
        "acknowledged",
        "escalated",
        "resolved",
        "false_positive",
    ]
    expected_state: Literal[
        "new",
        "notified",
        "acknowledged",
        "escalated",
        "resolved",
        "false_positive",
    ]
    note: str | None = Field(default=None, max_length=500)


class NotificationPreferenceUpdate(BaseModel):
    alert_category: str
    email: bool = True
    sms: bool = False
    min_severity: Literal["critical", "high", "medium", "low"] = "high"


class ThresholdUpdate(BaseModel):
    scope: Literal["global", "house", "device"]
    scope_id: int | None = None
    sound_type: str
    threshold: float = Field(ge=0.50, le=0.99)


class InferenceResult(BaseModel):
    event_id: int
    house_id: int
    device_id: int
    s3_key: str | None = None
    correlation_id: str | None = None
    predictions: list[dict[str, Any]]


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _serialize_alert(alert: Any, *, owner_view: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "alert_id": alert.alert_id,
        "event_id": alert.event_id,
        "house_id": alert.house_id,
        "room_id": alert.room_id,
        "device_id": alert.device_id,
        "alert_category": alert.alert_category,
        "sound_type": alert.sound_type,
        "severity": alert.severity,
        "state": alert.state,
        "suppressed_count": alert.suppressed_count,
        "version": alert.version,
        "created_at": _iso(alert.created_at),
        "updated_at": _iso(alert.updated_at),
    }
    if not owner_view:
        payload["confidence"] = float(alert.confidence) if alert.confidence is not None else None
    return payload


def _owner_view(claims: Claims) -> bool:
    return claims.role != "admin"


def _check_house_scope(claims: Claims, house_id: int) -> None:
    if claims.role != "admin" and house_id not in claims.house_ids:
        raise ForbiddenError("House out of scope")


def _serialize_detail(bundle: dict[str, Any], *, owner_view: bool) -> dict[str, Any]:
    payload = _serialize_alert(bundle["alert"], owner_view=owner_view)
    payload["history"] = [
        {
            "history_id": row.history_id,
            "from_state": row.from_state,
            "to_state": row.to_state,
            "actor_user_id": row.actor_user_id,
            "note": row.note,
            "changed_at": _iso(row.changed_at),
        }
        for row in bundle["history"]
    ]
    payload["deliveries"] = [
        {
            "notification_id": row.notification_id,
            "recipient_id": row.recipient_id,
            "recipient_label": row.recipient_label,
            "channel": row.channel,
            "status": row.status,
            "attempts": row.attempts,
            "last_error": row.last_error,
            "sent_at": _iso(row.sent_at),
        }
        for row in bundle["deliveries"]
    ]
    return payload


@router.get("/api/alerts")
def list_alerts(
    house_id: int | None = Query(default=None),
    category: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    state: str | None = Query(default=None),
    sound_type: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    min_confidence: float | None = Query(default=None, ge=0, le=1),
    max_confidence: float | None = Query(default=None, ge=0, le=1),
    q: str | None = Query(default=None, max_length=100),
    updated_since: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    result = AlertRepository(db).list(
        {
            "house_id": house_id,
            "category": category,
            "severity": severity,
            "state": state,
            "sound_type": sound_type,
            "updated_since": updated_since,
            "from": from_date,
            "to": to_date,
            "min_confidence": min_confidence,
            "max_confidence": max_confidence,
            "q": q,
        },
        page,
        claims,
        page_size=page_size,
    )
    return {
        **result,
        "items": [
            _serialize_alert(alert, owner_view=_owner_view(claims)) for alert in result["items"]
        ],
    }


@router.get("/api/alerts/export")
def export_alerts(
    format: Literal["csv", "pdf"] = "csv",
    house_id: int | None = Query(default=None),
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> Response:
    if house_id is not None:
        _check_house_scope(claims, house_id)
    result = AlertRepository(db).list({"house_id": house_id}, 1, claims, page_size=100)
    rows = result["items"]
    if format == "csv":
        output = StringIO()
        output.write("alert_id,house_id,sound_type,category,severity,state,confidence,created_at\n")
        for alert in rows:
            values = [
                alert.alert_id,
                alert.house_id,
                alert.sound_type or "",
                alert.alert_category,
                alert.severity,
                alert.state,
                "" if _owner_view(claims) else alert.confidence,
                _iso(alert.created_at) or "",
            ]
            output.write(
                ",".join('"' + str(value).replace('"', '""') + '"' for value in values)
                + "\n"
            )
        return Response(
            output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=alerts.csv"},
        )
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise DependencyUnavailableError("PDF export dependency is unavailable") from exc
    buffer = StringIO()
    # Keep the MVP export text-based and dependency-light; the full UI supplies formatting.
    buffer.write("Smart Home Alerts\n\n")
    for alert in rows:
        buffer.write(f"{alert.alert_id} {alert.sound_type} {alert.severity} {alert.state}\n")
    pdf_buffer = __import__("io").BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=letter)
    y = 760
    for line in buffer.getvalue().splitlines():
        pdf.drawString(40, y, line[:110])
        y -= 16
        if y < 40:
            pdf.showPage()
            y = 760
    pdf.save()
    return Response(
        pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=alerts.pdf"},
    )


@router.get("/api/stats/alerts")
def alert_stats(
    house_id: int | None = Query(default=None),
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    if house_id is not None:
        _check_house_scope(claims, house_id)
    filters: dict[str, Any] = {"house_id": house_id}
    if claims.role != "admin":
        filters["house_ids"] = claims.house_ids
    return AlertRepository(db).stats(**filters)


@router.get("/api/stats/false-alerts")
def false_alert_stats(
    house_id: int | None = Query(default=None),
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    if house_id is not None:
        _check_house_scope(claims, house_id)
    filters: dict[str, Any] = {"house_id": house_id}
    if claims.role != "admin":
        filters["house_ids"] = claims.house_ids
    return {"items": AlertRepository(db).false_alert_stats(**filters)}


@router.get("/api/notification-prefs")
def get_notification_preferences(
    house_id: int,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    _check_house_scope(claims, house_id)
    rows = PrefsRepository(db).get_for_user_house(claims.user_id, house_id)
    return {"house_id": house_id, "items": [
        {
            "alert_category": row.alert_category,
            "email": row.email,
            "sms": row.sms,
            "min_severity": row.min_severity,
        }
        for row in rows
    ]}


@router.put("/api/notification-prefs")
def update_notification_preferences(
    house_id: int,
    preferences: list[NotificationPreferenceUpdate],
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    _check_house_scope(claims, house_id)
    rows = PrefsRepository(db).upsert(
        claims.user_id, house_id, [item.model_dump() for item in preferences]
    )
    return {
        "house_id": house_id,
        "items": [
            {
                "alert_category": row.alert_category,
                "email": row.email,
                "sms": row.sms,
                "min_severity": row.min_severity,
            }
            for row in rows
        ],
    }


@router.get("/api/admin/thresholds")
def get_thresholds(
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    if claims.role != "admin":
        raise ForbiddenError("Admin role required")
    return {
        "items": [
            {
                "id": row.id,
                "scope": row.scope,
                "scope_id": row.scope_id,
                "sound_type": row.sound_type,
                "threshold": float(row.threshold),
            }
            for row in ThresholdRepository(db).list()
        ]
    }


@router.put("/api/admin/thresholds")
def update_threshold(
    body: ThresholdUpdate,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    if claims.role != "admin":
        raise ForbiddenError("Admin role required")
    if body.scope == "global" and body.scope_id is not None:
        raise UnprocessableError("Global threshold cannot have scope_id")
    if body.scope != "global" and body.scope_id is None:
        raise UnprocessableError("House and device thresholds require scope_id")
    row = ThresholdRepository(db).upsert(
        scope=body.scope,
        scope_id=body.scope_id,
        sound_type=body.sound_type,
        threshold=body.threshold,
        user_id=claims.user_id,
    )
    return {
        "id": row.id,
        "scope": row.scope,
        "scope_id": row.scope_id,
        "sound_type": row.sound_type,
        "threshold": float(row.threshold),
    }


@router.post("/internal/inference-results")
def internal_inference_result(
    body: InferenceResult,
    x_internal_key: str | None = Header(default=None),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.internal_api_enabled or x_internal_key != settings.internal_api_key:
        raise ForbiddenError("Internal API key required")
    overrides = ThresholdRepository(db).as_mappings()
    engine = PolicyEngine(
        event_repository=EventRepository(db),
        device_repository=DeviceRepository(db),
        alert_repository=AlertRepository(db),
        inference_log_repository=InferenceLogRepository(),
        threshold_resolver=ThresholdResolver(
            device_overrides=overrides["device"],
            house_overrides=overrides["house"],
            global_overrides=overrides["global"],
            default=settings.default_threshold,
        ),
    )
    result = engine.handle(body.model_dump())
    return {"event_id": result.event_id, "decision": result.decision, "alert_id": result.alert_id}


@router.get("/api/alerts/{alert_id}")
def get_alert(
    alert_id: int,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    bundle = AlertRepository(db).get_detail_bundle(alert_id, claims)
    return _serialize_detail(bundle, owner_view=_owner_view(claims))


@router.patch("/api/alerts/{alert_id}/state")
def update_alert_state(
    alert_id: int,
    body: AlertStateUpdate,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    repository = AlertRepository(db)
    repository.get_detail(alert_id, claims)
    updated = AlertStateService(repository).transition(
        alert_id,
        current_state=body.expected_state,
        next_state=body.to_state,
        role=claims.role or "",
        actor=claims.user_id,
        note=body.note,
    )
    return _serialize_alert(updated, owner_view=_owner_view(claims))


@router.post("/api/alerts/{alert_id}/resend")
def resend_alert_notifications(
    alert_id: int,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    if claims.role != "admin":
        from app.core.errors import ForbiddenError

        raise ForbiddenError("Admin role required")
    alert = AlertRepository(db).get_detail(alert_id, claims)
    accepted = NotificationDispatcher(NotificationRepository(db)).resend_failed(alert)
    return {"alert_id": alert_id, "accepted": accepted}
