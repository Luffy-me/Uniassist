"""Document corpus routes."""

from __future__ import annotations

from collections import Counter
from datetime import date

from fastapi import APIRouter, File, Form, UploadFile

from uniassist.api.dependencies import AdminDep, RequestIdDep, ServicesDep
from uniassist.api.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    map_service_exception,
)
from uniassist.api.schemas import (
    DocumentResponse,
    DocumentUploadResponse,
    IndexResponse,
    ProcessingResponse,
    document_response,
    index_response,
    processing_response,
)
from uniassist.documents.ingestion import IngestRequest
from uniassist.documents.models import DocumentRecord, DocumentStatus, SourceType
from uniassist.documents.validation import DEFAULT_MAX_FILE_SIZE_BYTES
from uniassist.processing.models import ProcessingStatus
from uniassist.processing.service import ProcessingEligibilityError

router = APIRouter(prefix="/documents", tags=["documents"])

_MISSING_RESOURCE_MARKERS = (
    "source file not found",
    "document not found",
)


_READ_CHUNK_BYTES = 1024 * 1024


async def _read_limited(file: UploadFile) -> bytes:
    """Read an upload, stopping as soon as it exceeds the size limit."""
    parts: list[bytes] = []
    total = 0
    while chunk := await file.read(_READ_CHUNK_BYTES):
        total += len(chunk)
        if total > DEFAULT_MAX_FILE_SIZE_BYTES:
            raise BadRequestError(
                f"file exceeds maximum size of {DEFAULT_MAX_FILE_SIZE_BYTES} bytes"
            )
        parts.append(chunk)
    return b"".join(parts)


def _is_missing_resource_error(error: str | None) -> bool:
    text = (error or "").lower()
    return any(marker in text for marker in _MISSING_RESOURCE_MARKERS)


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    services: ServicesDep,
    request_id: RequestIdDep,
    _: AdminDep,
    file: UploadFile = File(...),
    title: str = Form(...),
    source: str = Form(...),
    source_url: str = Form(..., min_length=1),
    version: str | None = Form(default=None),
    effective_date: date | None = Form(default=None),
    notes: str | None = Form(default=None),
) -> DocumentUploadResponse:
    content = await _read_limited(file)
    filename = file.filename or "document.txt"
    try:
        result = services.ingestion.ingest_bytes(
            filename=filename,
            content=content,
            request=IngestRequest(
                title=title,
                source=source,
                source_type=SourceType.ADMIN_UPLOAD,
                source_url=source_url,
                effective_date=effective_date,
                version=version,
                notes=notes,
            ),
        )
    except ValueError as exc:
        raise map_service_exception(exc) from exc

    return DocumentUploadResponse(
        request_id=request_id,
        document=_document_view(services, result.record),
        duplicate=result.duplicate,
    )


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    services: ServicesDep,
    _: AdminDep,
    status: DocumentStatus | None = None,
    verification_state: str | None = None,
    source: str | None = None,
) -> list[DocumentResponse]:
    records = services.ingestion.list_documents()
    chunk_counts = _chunk_counts(services)
    filtered = []
    for record in records:
        if status is not None and record.status != status:
            continue
        if (
            verification_state is not None
            and record.verification_state.value != verification_state
        ):
            continue
        if source is not None and record.source != source:
            continue
        filtered.append(_document_view(services, record, chunk_counts))
    return filtered


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    services: ServicesDep,
    _: AdminDep,
) -> DocumentResponse:
    record = services.ingestion.get_document(document_id)
    if record is None:
        raise NotFoundError(f"document not found: {document_id}")
    return _document_view(services, record)


@router.post("/{document_id}/activate", response_model=DocumentResponse)
def activate_document(
    document_id: str,
    services: ServicesDep,
    request_id: RequestIdDep,
    _: AdminDep,
) -> DocumentResponse:
    del request_id
    try:
        record = services.ingestion.activate(document_id)
    except KeyError as exc:
        raise NotFoundError(str(exc)) from exc
    except ValueError as exc:
        raise ConflictError(str(exc)) from exc
    return _document_view(services, record)


@router.post("/{document_id}/process", response_model=ProcessingResponse)
def process_document(
    document_id: str,
    services: ServicesDep,
    request_id: RequestIdDep,
    _: AdminDep,
) -> ProcessingResponse:
    try:
        result = services.processing.process_document(document_id)
    except ProcessingEligibilityError as exc:
        raise ConflictError(str(exc)) from exc
    if _is_missing_resource_error(result.error):
        raise NotFoundError(result.error)
    if result.status in (ProcessingStatus.FAILED, ProcessingStatus.UNSUPPORTED):
        raise ConflictError(result.error or f"processing {result.status.value}")
    return processing_response(request_id=request_id, result=result)


@router.post("/{document_id}/index", response_model=IndexResponse)
def index_document(
    document_id: str,
    services: ServicesDep,
    request_id: RequestIdDep,
    _: AdminDep,
) -> IndexResponse:
    try:
        result = services.indexing.index_document(document_id)
    except KeyError as exc:
        raise NotFoundError(str(exc)) from exc
    except ValueError as exc:
        raise map_service_exception(exc) from exc
    return index_response(request_id=request_id, result=result)


@router.post("/{document_id}/archive", response_model=DocumentResponse)
def archive_document(
    document_id: str,
    services: ServicesDep,
    _: AdminDep,
) -> DocumentResponse:
    """Retire a document and remove it from the searchable index."""
    try:
        record = services.ingestion.archive(document_id)
    except KeyError as exc:
        raise NotFoundError(str(exc)) from exc
    services.indexing.remove_document(document_id)
    return _document_view(services, record)


@router.post("/{document_id}/publish", response_model=DocumentResponse)
def publish_document(
    document_id: str,
    services: ServicesDep,
    request_id: RequestIdDep,
    _: AdminDep,
) -> DocumentResponse:
    del request_id
    previous = services.ingestion.get_document(document_id)
    if previous is None:
        raise NotFoundError(f"document not found: {document_id}")

    try:
        services.ingestion.activate(document_id)
    except ValueError as exc:
        raise ConflictError(str(exc)) from exc

    try:
        _process_and_index(services, document_id)
    except Exception:
        # Do not leave a document verified/active without a usable index.
        services.ingestion.restore(previous)
        raise

    record = services.ingestion.get_document(document_id)
    if record is None:
        raise NotFoundError(f"document not found: {document_id}")
    return _document_view(services, record)


def _process_and_index(services: ServicesDep, document_id: str) -> None:
    try:
        processed = services.processing.process_document(document_id)
    except ProcessingEligibilityError as exc:
        raise ConflictError(str(exc)) from exc

    if _is_missing_resource_error(processed.error):
        raise NotFoundError(processed.error)
    if processed.status != ProcessingStatus.COMPLETED:
        raise ConflictError(
            processed.error or f"processing {processed.status.value}"
        )

    try:
        services.indexing.index_document(document_id)
    except KeyError as exc:
        raise NotFoundError(str(exc)) from exc
    except ValueError as exc:
        raise map_service_exception(exc) from exc


def _chunk_counts(services: ServicesDep) -> Counter[str]:
    return Counter(
        chunk.document_id for chunk in services.indexing.vector_store.list_chunks()
    )


def _document_view(
    services: ServicesDep,
    record: DocumentRecord,
    chunk_counts: Counter[str] | None = None,
) -> DocumentResponse:
    processing = services.processing.processing_store.get_result(record.document_id)
    counts = chunk_counts if chunk_counts is not None else _chunk_counts(services)
    chunks = counts.get(record.document_id, 0)
    return document_response(
        record,
        processing_status=processing.status.value if processing else None,
        processing_error=processing.error if processing else None,
        indexed=chunks > 0,
        chunks_indexed=chunks or None,
    )
