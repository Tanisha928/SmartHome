"""MVP alert endpoints for listing, inspection, and state transitions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.alerts.alert_state_service import AlertStateService
from app.alerts.notification_dispatcher import NotificationDispatcher
from app.core.deps import Claims, get_db, require_user
from app.persistence.repositories.alert_repo import AlertRepository
from app.persistence.repositories.notification_repo import NotificationRepository

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


@router.get("/api/alerts")
def list_alerts(
    house_id: int | None = Query(default=None),
    category: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    state: str | None = Query(default=None),
    sound_type: str | None = Query(default=None),
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
        },
        page,
        claims,
        page_size=page_size,
    )
    return {
        **result,
        "items": [_serialize_alert(alert, owner_view=_owner_view(claims)) for alert in result["items"]],
    }


@router.get("/api/alerts/{alert_id}")
def get_alert(
    alert_id: int,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    alert = AlertRepository(db).get_detail(alert_id, claims)
    return _serialize_alert(alert, owner_view=_owner_view(claims))


@router.patch("/api/alerts/{alert_id}/state")
def update_alert_state(
    alert_id: int,
    body: AlertStateUpdate,
    claims: Claims = Depends(require_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    repository = AlertRepository(db)
    alert = repository.get_detail(alert_id, claims)
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
