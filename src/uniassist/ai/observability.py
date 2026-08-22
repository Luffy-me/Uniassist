"""Safe observability helpers for AI requests."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger("uniassist.ai")


@dataclass(frozen=True)
class RequestLogContext:
    """Safe metadata for AI request logging."""

    request_id: str
    question_hash: str
    chunk_count: int
    model: str
    started_at: datetime
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    top_score: float | None = None


def question_hash(text: str) -> str:
    """Return a non-reversible hash identifier for a question."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def new_request_context(
    question: str,
    *,
    model: str,
    chunk_count: int,
    embedding_model: str | None = None,
    embedding_dimension: int | None = None,
    top_score: float | None = None,
) -> RequestLogContext:
    return RequestLogContext(
        request_id=hashlib.sha256(
            f"{question}:{datetime.now(UTC).isoformat()}".encode()
        ).hexdigest()[:12],
        question_hash=question_hash(question),
        chunk_count=chunk_count,
        model=model,
        started_at=datetime.now(UTC),
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        top_score=top_score,
    )


def log_request_start(context: RequestLogContext) -> None:
    logger.info(
        "ai_request_start request_id=%s question_hash=%s chunks=%s model=%s "
        "embedding_model=%s embedding_dimension=%s top_score=%s",
        context.request_id,
        context.question_hash,
        context.chunk_count,
        context.model,
        context.embedding_model or "-",
        context.embedding_dimension if context.embedding_dimension is not None else "-",
        f"{context.top_score:.4f}" if context.top_score is not None else "-",
    )


def log_request_end(
    context: RequestLogContext,
    *,
    verified: bool,
    failure_type: str | None = None,
    generation_latency_ms: float | None = None,
    verification_latency_ms: float | None = None,
    latency_ms: float | None = None,
) -> None:
    logger.info(
        "ai_request_end request_id=%s verified=%s failure_type=%s "
        "generation_latency_ms=%s verification_latency_ms=%s latency_ms=%s model=%s",
        context.request_id,
        verified,
        failure_type or "-",
        f"{generation_latency_ms:.1f}"
        if generation_latency_ms is not None
        else "-",
        f"{verification_latency_ms:.1f}"
        if verification_latency_ms is not None
        else "-",
        f"{latency_ms:.1f}" if latency_ms is not None else "-",
        context.model,
    )
