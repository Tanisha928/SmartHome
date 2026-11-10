"""Admin data APIs — health, events, retry, inference-logs, audit, retention."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.deps import Claims, get_db, require_role
from app.core.errors import ConflictError, NotFoundError
from app.persistence.jobs.retention_job import RetentionJob
from app.persistence.pg.models import BackupStatus
from app.persistence.queue.publisher import QueuePublisher
from app.persistence.repositories.audit_repo import AuditRepository
from app.persistence.repositories.event_repo import EventRepository
from app.persistence.repositories.inference_log_repo import InferenceLogRepository
from app.persistence.repositories.retention_repo import RetentionRepository

admin_only = require_role("admin")
router = APIRouter(tags=["admin-data"])


def _health(db: Any) -> dict[str, Any]:
    settings = get_settings()
    postgres = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        postgres = "down"

    mongo = "ok"
    try:
        from app.persistence.mongo.client import get_mongo_client

        get_mongo_client().admin.command("ping")
    except Exception:
        mongo = "down"

    s3 = "ok"
    try:
        from app.persistence.s3.clip_store import _s3_client

        _s3_client().head_bucket(Bucket=settings.s3_bucket)
    except Exception:
        s3 = "down" if settings.aws_endpoint_url else "unknown"

    pub = QueuePublisher()
    q = pub.get_queue_attributes(settings.sqs_queue_url) if settings.sqs_queue_url else {}
    dlq = pub.get_queue_attributes(settings.sqs_dlq_url) if settings.sqs_dlq_url else {}

    backups = list(
        db.scalars(select(BackupStatus).order_by(BackupStatus.taken_at.desc()).limit(10)).all()
    )
    rds_age_h = None
    mongo_age_d = None
    now = datetime.now(UTC)
    for b in backups:
        if b.kind == "rds_snapshot" and b.taken_at and rds_age_h is None:
            taken = b.taken_at if b.taken_at.tzinfo else b.taken_at.replace(tzinfo=UTC)
            rds_age_h = round((now - taken).total_seconds() / 3600, 1)
        if b.kind == "mongo_dump" and b.taken_at and mongo_age_d is None:
            taken = b.taken_at if b.taken_at.tzinfo else b.taken_at.replace(tzinfo=UTC)
            mongo_age_d = round((now - taken).total_seconds() / 86400, 1)

    unprocessed = EventRepository(db).count_unprocessed()
    return {
        "postgres": postgres,
        "mongo": mongo,
        "s3": s3,
        "sqs": {
            "visible": int(q.get("ApproximateNumberOfMessages", 0) or 0),
            "in_flight": int(q.get("ApproximateNumberOfMessagesNotVisible", 0) or 0),
        },
        "dlq": {"visible": int(dlq.get("ApproximateNumberOfMessages", 0) or 0)},
        "backups": {"rds_snapshot_age_h": rds_age_h, "mongo_dump_age_d": mongo_age_d},
        "unprocessed_events": unprocessed,
    }


@router.get("/api/admin/data/health")
def data_health(
    claims: Claims = Depends(admin_only),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    return _health(db)


@router.get("/api/admin/events")
def list_events(
    state: str | None = None,
    house_id: int | None = None,
    age_minutes: int | None = None,
    page: int = 1,
    page_size: int = 25,
    claims: Claims = Depends(admin_only),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    age = timedelta(minutes=age_minutes) if age_minutes is not None else None
    result = EventRepository(db).list_admin(state, house_id, age, page, page_size=page_size)
    items = [
        {
            "event_id": e.event_id,
            "house_id": e.house_id,
            "device_id": e.device_id,
            "processing_state": e.processing_state,
            "retry_count": e.retry_count,
            "s3_key": e.s3_key,
            "captured_at": e.captured_at.isoformat().replace("+00:00", "Z"),
            "correlation_id": e.correlation_id,
        }
        for e in result["items"]
    ]
    return {**result, "items": items}


@router.post("/api/admin/events/{event_id}/retry")
def retry_event(
    event_id: int,
    claims: Claims = Depends(admin_only),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    repo = EventRepository(db)
    event = repo.get(event_id)
    if event is None:
        raise NotFoundError("Event not found")
    if event.processing_state == "scored":
        raise ConflictError("Event already scored", details={"error": "already_scored"})
    event = repo.requeue(event_id)
    mid = QueuePublisher().publish_inference_event(
        event_id=event.event_id,
        house_id=event.house_id,
        device_id=event.device_id,
        s3_key=event.s3_key or "",
        captured_at=event.captured_at,
        correlation_id=event.correlation_id or "",
    )
    if mid:
        event.last_published_at = datetime.now(UTC)
        db.flush()
    return {
        "event_id": event.event_id,
        "processing_state": event.processing_state,
        "published": bool(mid),
    }


@router.get("/api/admin/inference-logs")
def inference_logs(
    house_id: int | None = None,
    model_version: str | None = None,
    label: str | None = None,
    page: int = 1,
    page_size: int = 25,
    claims: Claims = Depends(admin_only),
) -> dict[str, Any]:
    filters = {"house_id": house_id, "model_version": model_version, "label": label}
    return InferenceLogRepository().query(filters, page, page_size=page_size)


@router.get("/api/admin/audit")
def audit_log(
    house_id: int | None = None,
    actor: int | None = None,
    action: str | None = None,
    page: int = 1,
    page_size: int = 25,
    export: str | None = Query(default=None),
    claims: Claims = Depends(admin_only),
    db: Any = Depends(get_db),
) -> Any:
    result = AuditRepository(db).query(house_id, actor, action, None, page, page_size=page_size)
    items = [
        {
            "audit_id": a.audit_id,
            "actor_user_id": a.actor_user_id,
            "house_id": a.house_id,
            "action": a.action,
            "resource": a.resource,
            "ts": a.ts.isoformat().replace("+00:00", "Z") if a.ts else None,
            "correlation_id": a.correlation_id,
        }
        for a in result["items"]
    ]
    if export == "csv":
        lines = ["audit_id,actor_user_id,house_id,action,resource,ts,correlation_id"]
        for row in items:
            lines.append(
                ",".join(
                    str(row.get(k) or "")
                    for k in (
                        "audit_id",
                        "actor_user_id",
                        "house_id",
                        "action",
                        "resource",
                        "ts",
                        "correlation_id",
                    )
                )
            )
        return PlainTextResponse("\n".join(lines) + "\n", media_type="text/csv")
    return {**result, "items": items}


@router.get("/api/admin/retention")
def get_retention(
    claims: Claims = Depends(admin_only),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    p = RetentionRepository(db).get()
    return {
        "clip_expire_days": p.clip_expire_days,
        "clip_ia_transition_days": p.clip_ia_transition_days,
        "telemetry_ttl_days": p.telemetry_ttl_days,
        "updated_by": p.updated_by,
        "updated_at": p.updated_at.isoformat().replace("+00:00", "Z") if p.updated_at else None,
    }


@router.put("/api/admin/retention")
def put_retention(
    body: dict[str, Any],
    claims: Claims = Depends(admin_only),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    p = RetentionRepository(db).put(updated_by=claims.user_id, **body)
    return {
        "clip_expire_days": p.clip_expire_days,
        "clip_ia_transition_days": p.clip_ia_transition_days,
        "telemetry_ttl_days": p.telemetry_ttl_days,
    }


@router.post("/api/admin/retention/run")
def run_retention_job(
    claims: Claims = Depends(admin_only),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    return RetentionJob(db).run()
