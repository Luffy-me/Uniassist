"""FastAPI application factory."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from uniassist import __version__
from uniassist.ai.pipeline import AnswerPipeline
from uniassist.api.dependencies import (
    AppServices,
    AppSettings,
    build_services,
    load_settings,
    resolve_request_id,
)
from uniassist.api.errors import register_exception_handlers
from uniassist.api.routes import ask, documents, health


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a safe request ID to every request."""

    async def dispatch(self, request: Request, call_next):
        request.state.request_id = resolve_request_id(
            request.headers.get("X-Request-ID")
        )
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request.state.request_id
        _log_request(request, response.status_code, duration_ms)
        return response


def create_app(
    *,
    project_root: Path | None = None,
    settings: AppSettings | None = None,
    services: AppServices | None = None,
    pipeline: AnswerPipeline | None = None,
    processing_require_eligibility: bool = True,
) -> FastAPI:
    """Create a testable FastAPI application."""
    resolved_settings = settings or load_settings(project_root)
    if services is None:
        services = build_services(
            resolved_settings,
            pipeline=pipeline,
            processing_require_eligibility=processing_require_eligibility,
        )

    app = FastAPI(
        title="UniAssist API",
        version=__version__,
        description="REST API for the UniAssist university knowledge assistant.",
    )
    app.state.settings = resolved_settings
    app.state.services = services

    register_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware)

    if resolved_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved_settings.cors_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )

    app.include_router(health.router)
    app.include_router(ask.router)
    app.include_router(documents.router)
    return app


def _log_request(request: Request, status_code: int, duration_ms: float) -> None:
    import logging

    logger = logging.getLogger("uniassist.api")
    logger.info(
        "api_request request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request.state.request_id,
        request.method,
        request.url.path,
        status_code,
        duration_ms,
    )
