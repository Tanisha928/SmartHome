"""Correlation-id middleware and access logging."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

CORRELATION_HEADER = "X-Correlation-Id"
log = get_logger("access")


def new_correlation_id() -> str:
    return f"c-{uuid.uuid4().hex[:16]}"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        cid = request.headers.get(CORRELATION_HEADER) or new_correlation_id()
        request.state.correlation_id = cid
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=cid)

        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        response.headers[CORRELATION_HEADER] = cid
        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        return response
