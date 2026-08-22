"""Health and status routes."""

from __future__ import annotations

import os

from fastapi import APIRouter, Request

from uniassist import __version__
from uniassist.ai.providers.nvidia_config import (
    check_nvidia_health,
    resolve_api_key,
    resolve_base_url,
    resolve_chat_model,
    resolve_embedding_model,
)
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
    base_url = resolve_base_url()
    chat_model: str | None = None
    embedding_model: str | None = None
    nvidia_configured = False
    nvidia_embedding_configured = False

    try:
        api_key = resolve_api_key(base_url)
        chat_model = _safe_chat_model(base_url=base_url, api_key=api_key)
        embedding_model = _safe_embedding_model(base_url=base_url, api_key=api_key)
        nvidia_configured = chat_model is not None
        nvidia_embedding_configured = embedding_model is not None
    except Exception:
        pass

    health_status = check_nvidia_health(
        base_url=base_url,
        chat_model=chat_model,
        embedding_model=embedding_model,
    )
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
        nvidia_configured=nvidia_configured,
        nvidia_embedding_configured=nvidia_embedding_configured,
        nvidia_base_url=base_url,
        nvidia_chat_model=chat_model,
        nvidia_embedding_model=embedding_model or stats.embedding_model,
        nvidia_reachable=health_status.reachable,
        nvidia_health_message=health_status.message,
        storage_backend=storage_backend,
        appwrite_configured=appwrite_configured,
    )


def _safe_chat_model(*, base_url: str, api_key: str) -> str | None:
    configured = (
        os.environ.get("NVIDIA_CHAT_MODEL", "").strip()
        or os.environ.get("NVIDIA_MODEL", "").strip()
    )
    if configured:
        return configured
    try:
        return resolve_chat_model(base_url=base_url, api_key=api_key)
    except Exception:
        return None


def _safe_embedding_model(*, base_url: str, api_key: str) -> str | None:
    configured = os.environ.get("NVIDIA_EMBEDDING_MODEL", "").strip()
    if configured:
        return configured
    try:
        return resolve_embedding_model(base_url=base_url, api_key=api_key)
    except Exception:
        return None
