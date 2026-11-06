"""FastAPI application factory — mounts auth + houses; ingest mounts later."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.api import router as auth_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import CorrelationIdMiddleware
from app.persistence.api.houses import router as houses_router
from app.persistence.api.ingest import router as ingest_router

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.env != "test":
        try:
            from app.persistence.mongo.client import ensure_indexes

            ensure_indexes()
        except Exception as exc:  # pragma: no cover - mongo may be down in unit tests
            log.warning("mongo_indexes_skipped", error=str(exc))
    yield


def create_app() -> FastAPI:
    configure_logging(json_logs=True)
    settings = get_settings()

    app = FastAPI(
        title="Smart Home Platform API",
        version="0.2.0",
        description="Intelligent Cloud Platform for Smart Homes",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-Id"],
    )
    app.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(app)

    app.include_router(auth_router)
    app.include_router(houses_router)
    app.include_router(ingest_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
