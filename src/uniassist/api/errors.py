"""API error types and exception handlers."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from uniassist.ai.generation import GenerationError
from uniassist.ai.providers.groq import GroqAPIError, GroqConfigError
from uniassist.processing.service import ProcessingEligibilityError
from uniassist.rag.index_metadata import IndexCompatibilityError
from uniassist.rag.indexing import IndexingEligibilityError


@dataclass(frozen=True)
class ErrorResponse:
    """Standard API error payload."""

    request_id: str
    error: str
    detail: str


class BadRequestError(Exception):
    """Invalid client request."""


class NotFoundError(Exception):
    """Requested resource was not found."""


class ConflictError(Exception):
    """Request conflicts with current resource state."""


class ServiceUnavailableError(Exception):
    """Upstream AI or dependency is unavailable."""


class UnauthorizedError(Exception):
    """Admin authentication is missing or invalid."""


def register_exception_handlers(app: FastAPI) -> None:
    """Register consistent HTTP error handlers."""

    @app.exception_handler(BadRequestError)
    async def bad_request_handler(
        request: Request,
        exc: BadRequestError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=400,
            error="bad_request",
            detail=str(exc),
        )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(
        request: Request,
        exc: NotFoundError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=404,
            error="not_found",
            detail=str(exc),
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(
        request: Request,
        exc: ConflictError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=409,
            error="conflict",
            detail=str(exc),
        )

    @app.exception_handler(ServiceUnavailableError)
    async def service_unavailable_handler(
        request: Request,
        exc: ServiceUnavailableError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=503,
            error="service_unavailable",
            detail=str(exc),
        )

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_handler(
        request: Request,
        exc: UnauthorizedError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=401,
            error="unauthorized",
            detail=str(exc),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=422,
            error="validation_error",
            detail=_validation_detail(exc),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        request: Request,
        exc: ValueError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=400,
            error="bad_request",
            detail=str(exc),
        )

    @app.exception_handler(KeyError)
    async def key_error_handler(
        request: Request,
        exc: KeyError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=404,
            error="not_found",
            detail=str(exc),
        )

    @app.exception_handler(Exception)
    async def internal_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        _log_internal_error(request, exc)
        return _error_response(
            request,
            status_code=500,
            error="internal_error",
            detail="An unexpected internal error occurred.",
        )


def map_service_exception(exc: Exception) -> Exception:
    """Map domain exceptions to API-layer exceptions."""
    if isinstance(exc, KeyError):
        return NotFoundError(str(exc))
    if isinstance(
        exc,
        (
            IndexingEligibilityError,
            ProcessingEligibilityError,
            IndexCompatibilityError,
        ),
    ):
        return ConflictError(str(exc))
    if isinstance(
        exc,
        (
            GenerationError,
            GroqConfigError,
            GroqAPIError,
        ),
    ):
        return ServiceUnavailableError(str(exc))
    if isinstance(exc, ValueError):
        return BadRequestError(str(exc))
    return exc


def _error_response(
    request: Request,
    *,
    status_code: int,
    error: str,
    detail: str,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    payload = ErrorResponse(
        request_id=request_id,
        error=error,
        detail=detail,
    )
    return JSONResponse(
        status_code=status_code,
        content={
            "request_id": payload.request_id,
            "error": payload.error,
            "detail": payload.detail,
        },
    )


def _validation_detail(exc: RequestValidationError) -> str:
    messages = []
    for item in exc.errors():
        location = ".".join(str(part) for part in item.get("loc", ()))
        message = item.get("msg", "invalid value")
        messages.append(f"{location}: {message}" if location else message)
    return "; ".join(messages) or "validation failed"


def _log_internal_error(request: Request, exc: Exception) -> None:
    import logging

    logger = logging.getLogger("uniassist.api")
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(
        "api_internal_error request_id=%s path=%s",
        request_id,
        request.url.path,
        exc_info=exc,
    )
