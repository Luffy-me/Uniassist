"""FastAPI dependency injection and application services."""

from __future__ import annotations

import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request

from uniassist.ai.pipeline import AnswerPipeline
from uniassist.documents.ingestion import DocumentIngestionService
from uniassist.processing.service import DocumentProcessingService
from uniassist.rag.indexing import IndexingService

logger = logging.getLogger("uniassist.api")

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9\-]{8,64}$")


@dataclass
class AppSettings:
    """Runtime configuration for the API layer."""

    project_root: Path
    max_question_length: int = 2000
    cors_origins: tuple[str, ...] = ()


@dataclass
class AppServices:
    """Shared UniAssist services used by route handlers."""

    ingestion: DocumentIngestionService
    processing: DocumentProcessingService
    indexing: IndexingService
    pipeline: AnswerPipeline
    settings: AppSettings


def load_settings(project_root: Path | None = None) -> AppSettings:
    root = project_root or Path(
        os.environ.get("UNIASSIST_PROJECT_ROOT", Path.cwd())
    )
    cors_raw = os.environ.get("UNIASSIST_CORS_ORIGINS", "").strip()
    cors_origins = tuple(
        origin.strip()
        for origin in cors_raw.split(",")
        if origin.strip()
    )
    return AppSettings(
        project_root=root,
        max_question_length=int(
            os.environ.get("UNIASSIST_MAX_QUESTION_LENGTH", "2000")
        ),
        cors_origins=cors_origins,
    )


def build_services(
    settings: AppSettings,
    *,
    pipeline: AnswerPipeline | None = None,
    processing_require_eligibility: bool = True,
) -> AppServices:
    root = settings.project_root
    ingestion = DocumentIngestionService.default(root)
    processing = DocumentProcessingService.default(
        root,
        require_eligibility=processing_require_eligibility,
    )
    indexing = IndexingService.default(root)
    resolved_pipeline = pipeline or AnswerPipeline.from_indexing(indexing, root)
    return AppServices(
        ingestion=ingestion,
        processing=processing,
        indexing=indexing,
        pipeline=resolved_pipeline,
        settings=settings,
    )


def get_services(request: Request) -> AppServices:
    services = request.app.state.services
    if services is None:
        raise RuntimeError("application services are not configured")
    return services


def get_request_id(request: Request) -> str:
    return request.state.request_id


ServicesDep = Annotated[AppServices, Depends(get_services)]
RequestIdDep = Annotated[str, Depends(get_request_id)]


def resolve_request_id(header_value: str | None) -> str:
    if header_value and REQUEST_ID_PATTERN.fullmatch(header_value.strip()):
        return header_value.strip()
    return uuid.uuid4().hex
