"""Ingest and event lookup endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from app.core.deps import Claims, get_claims, get_db, require_device
from app.core.errors import NotFoundError
from app.persistence.ingest.service import IngestService
from app.persistence.repositories.event_repo import EventRepository

router = APIRouter(tags=["ingest"])


@router.post("/api/ingest/events")
async def ingest_event(
    request: Request,
    house_id: int = Form(...),
    device_id: int = Form(...),
    captured_at: datetime = Form(...),
    duration_sec: float | None = Form(None),
    clip: UploadFile = File(...),
    claims: Claims = Depends(require_device),
    db: Any = Depends(get_db),
) -> JSONResponse:
    if duration_sec is not None and duration_sec <= 0:
        from app.core.errors import AppError

        raise AppError("duration_sec must be > 0", details={"error": "invalid_duration"})

    data = await clip.read()
    cid = getattr(request.state, "correlation_id", None)
    body, status = IngestService(db).handle(
        claims=claims,
        house_id=house_id,
        device_id=device_id,
        captured_at=captured_at,
        clip_bytes=data,
        content_type=clip.content_type or "application/octet-stream",
        duration_sec=duration_sec,
        correlation_id=cid,
        filename=clip.filename,
    )
    return JSONResponse(content=body, status_code=status)


@router.get("/api/events/{event_id}")
def get_event(
    event_id: int,
    claims: Claims = Depends(get_claims),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    event = EventRepository(db).get(event_id)
    if event is None:
        raise NotFoundError("Event not found")
    # scope check
    if claims.type == "device" and (
        claims.device_id != event.device_id or claims.house_id != event.house_id
    ):
        from app.core.errors import ForbiddenError

        raise ForbiddenError("Event out of scope")
    if claims.type == "user" and claims.role != "admin":
        if event.house_id not in claims.house_ids:
            from app.core.errors import ForbiddenError

            raise ForbiddenError("Event out of scope")
    return {
        "event_id": event.event_id,
        "device_id": event.device_id,
        "house_id": event.house_id,
        "s3_key": event.s3_key,
        "processing_state": event.processing_state,
        "retry_count": event.retry_count,
        "captured_at": event.captured_at.isoformat().replace("+00:00", "Z"),
        "correlation_id": event.correlation_id,
        "decision": event.decision,
    }
