"""Health and status routes."""

from __future__ import annotations

import os

from fastapi import APIRouter, Request

from uniassist import __version__
from uniassist.api.dependencies import RequestIdDep, ServicesDep
from uniassist.api.schemas import HealthResponse, StatusResponse
from uniassist.persistence.config import AppwriteConfig, resolve_storage_backend

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get("/status", response_model=StatusResponse)
def status(
    request: Request,
    services: ServicesDep,
    request_id: RequestIdDep,
) -> StatusResponse:
    del request
    stats = services.indexing.stats()
    groq_configured = bool(os.environ.get("GROQ_API_KEY", "").strip())
    storage_backend = resolve_storage_backend().value
    appwrite_configured = AppwriteConfig.try_from_env() is not None

    return StatusResponse(
        request_id=request_id,
        application_version=__version__,
        embedding_provider=stats.provider_name,
        embedding_model=stats.embedding_model,
        embedding_dimension=stats.embedding_dimension,
        rag_available=stats.total_chunks > 0,
        indexed_documents=stats.indexed_documents,
        total_chunks=stats.total_chunks,
        chat_provider="groq",
        groq_configured=groq_configured,
        groq_chat_model=(
            os.environ.get("GROQ_CHAT_MODEL", "").strip() or None
        ),
        storage_backend=storage_backend,
        appwrite_configured=appwrite_configured,
    )
