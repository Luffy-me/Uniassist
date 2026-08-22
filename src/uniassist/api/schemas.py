"""FastAPI request and response schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from uniassist.ai.models import Citation, RefusalAnswer, RefusalReason, VerifiedAnswer
from uniassist.ai.models import VerificationResult as DomainVerificationResult
from uniassist.documents.models import DocumentRecord
from uniassist.processing.models import ProcessingResult
from uniassist.rag.indexing import IndexResult

MAX_QUESTION_LENGTH = 2000


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class StatusResponse(BaseModel):
    request_id: str
    application_version: str
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    rag_available: bool
    indexed_documents: int = 0
    total_chunks: int = 0
    nvidia_configured: bool
    nvidia_embedding_configured: bool
    nvidia_base_url: str | None = None
    nvidia_chat_model: str | None = None
    nvidia_embedding_model: str | None = None
    nvidia_reachable: bool | None = None
    nvidia_health_message: str | None = None


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_LENGTH)


class CitationResponse(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    page_number: int | None = None
    section: str | None = None
    source: str
    source_url: str | None = None
    label: str


class VerificationResponse(BaseModel):
    verified: bool
    confidence: float
    supported_claims: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    citation_errors: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    refusal_reason: str | None = None


class AskTimingsResponse(BaseModel):
    retrieval_latency_ms: float | None = None
    verification_latency_ms: float | None = None
    total_latency_ms: float | None = None


class AskResponse(BaseModel):
    request_id: str
    status: Literal["verified", "refused"]
    answer: str | None = None
    message: str | None = None
    model: str | None = None
    generated_at: datetime | None = None
    citations: list[CitationResponse] = Field(default_factory=list)
    verification: VerificationResponse
    timings: AskTimingsResponse = Field(default_factory=AskTimingsResponse)


class DocumentResponse(BaseModel):
    document_id: str
    title: str
    filename: str
    content_type: str
    sha256: str
    uploaded_at: datetime
    source: str
    source_type: str
    source_url: str | None = None
    effective_date: date | None = None
    version: str | None = None
    status: str
    verification_state: str
    notes: str | None = None
    processing_status: str | None = None
    indexed: bool = False
    chunks_indexed: int | None = None


class DocumentUploadResponse(BaseModel):
    request_id: str
    document: DocumentResponse
    duplicate: bool


class ProcessingResponse(BaseModel):
    request_id: str
    result: dict


class IndexResponse(BaseModel):
    request_id: str
    document_id: str
    chunks_indexed: int
    indexed_at: datetime


class ErrorBody(BaseModel):
    request_id: str
    error: str
    detail: str


def citation_response(citation: Citation) -> CitationResponse:
    return CitationResponse(
        chunk_id=citation.chunk_id,
        document_id=citation.document_id,
        title=citation.title,
        page_number=citation.page_number,
        section=citation.section,
        source=citation.source,
        source_url=citation.source_url,
        label=citation.display_label(),
    )


def verification_response(result: DomainVerificationResult) -> VerificationResponse:
    return VerificationResponse(
        verified=result.verified,
        confidence=result.confidence,
        supported_claims=list(result.supported_claims),
        unsupported_claims=list(result.unsupported_claims),
        contradictions=list(result.contradictions),
        citation_errors=list(result.citation_errors),
        reasoning_summary=result.reasoning_summary,
        refusal_reason=(
            result.refusal_reason.value if result.refusal_reason else None
        ),
    )


def ask_response_from_verified(
    *,
    request_id: str,
    answer: VerifiedAnswer,
    timings: AskTimingsResponse | None = None,
) -> AskResponse:
    return AskResponse(
        request_id=request_id,
        status="verified",
        answer=answer.answer_text,
        model=answer.model,
        generated_at=answer.generated_at,
        citations=[citation_response(item) for item in answer.citations],
        verification=verification_response(answer.verification_result),
        timings=timings or AskTimingsResponse(),
    )


def ask_response_from_refusal(
    *,
    request_id: str,
    answer: RefusalAnswer,
    timings: AskTimingsResponse | None = None,
) -> AskResponse:
    return AskResponse(
        request_id=request_id,
        status="refused",
        message=answer.message,
        model=answer.model,
        generated_at=answer.generated_at,
        citations=[],
        verification=verification_response(answer.verification_result),
        timings=timings or AskTimingsResponse(),
    )


def document_response(
    record: DocumentRecord,
    *,
    processing_status: str | None = None,
    indexed: bool = False,
    chunks_indexed: int | None = None,
) -> DocumentResponse:
    return DocumentResponse(
        document_id=record.document_id,
        title=record.title,
        filename=record.filename,
        content_type=record.content_type,
        sha256=record.sha256,
        uploaded_at=record.uploaded_at,
        source=record.source,
        source_type=record.source_type.value,
        source_url=record.source_url,
        effective_date=record.effective_date,
        version=record.version,
        status=record.status.value,
        verification_state=record.verification_state.value,
        notes=record.notes,
        processing_status=processing_status,
        indexed=indexed,
        chunks_indexed=chunks_indexed,
    )


def processing_response(
    *,
    request_id: str,
    result: ProcessingResult,
) -> ProcessingResponse:
    return ProcessingResponse(
        request_id=request_id,
        result=result.to_dict(),
    )


def index_response(*, request_id: str, result: IndexResult) -> IndexResponse:
    return IndexResponse(
        request_id=request_id,
        document_id=result.document_id,
        chunks_indexed=result.chunks_indexed,
        indexed_at=result.indexed_at,
    )


def refusal_reason_name(reason: RefusalReason | None) -> str | None:
    return reason.value if reason is not None else None
