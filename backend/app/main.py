"""FastAPI application factory — core middleware + health; routers mount later."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import CorrelationIdMiddleware


def create_app() -> FastAPI:
    configure_logging(json_logs=True)
    settings = get_settings()

    app = FastAPI(
        title="Smart Home Platform API",
        version="0.1.0",
        description="Intelligent Cloud Platform for Smart Homes",
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

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
