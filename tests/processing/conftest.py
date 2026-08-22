"""Shared fixtures for processing tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from uniassist.documents.ingestion import DocumentIngestionService, IngestRequest
from uniassist.documents.models import (
    DocumentRecord,
    DocumentStatus,
    SourceType,
    VerificationState,
)
from uniassist.documents.store import JsonDocumentStore
from uniassist.processing.service import DocumentProcessingService
from uniassist.processing.store import ProcessingStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def tmp_corpus(
    tmp_path: Path,
) -> tuple[DocumentIngestionService, DocumentProcessingService]:
    raw_dir = tmp_path / "raw"
    metadata_dir = tmp_path / "metadata"
    processed_dir = tmp_path / "processed"
    document_store = JsonDocumentStore(
        raw_dir=raw_dir,
        index_path=metadata_dir / "documents.json",
    )
    processing_store = ProcessingStore(
        processed_dir=processed_dir,
        index_path=metadata_dir / "processing.json",
    )
    ingestion = DocumentIngestionService(document_store)
    processing = DocumentProcessingService(
        document_store=document_store,
        processing_store=processing_store,
        require_eligibility=False,
    )
    return ingestion, processing


def activate_record(
    ingestion: DocumentIngestionService,
    document_id: str,
) -> DocumentRecord:
    return ingestion.activate(document_id)


def make_active_record(
    ingestion: DocumentIngestionService,
    path: Path,
    *,
    title: str = "Test Document",
    source: str = "Test source",
    source_url: str | None = "https://example.org/doc",
) -> DocumentRecord:
    uploaded = ingestion.ingest_file(
        path,
        IngestRequest(title=title, source=source, source_url=source_url),
    )
    return activate_record(ingestion, uploaded.record.document_id)


def build_record(
    *,
    document_id: str,
    filename: str,
    local_path: Path,
    sha256: str,
    status: DocumentStatus = DocumentStatus.ACTIVE,
    verification_state: VerificationState = VerificationState.VERIFIED,
) -> DocumentRecord:
    return DocumentRecord(
        document_id=document_id,
        title="Synthetic",
        filename=filename,
        content_type="application/octet-stream",
        sha256=sha256,
        local_path=local_path,
        uploaded_at=datetime.now(UTC),
        source="test",
        source_type=SourceType.ADMIN_UPLOAD,
        status=status,
        verification_state=verification_state,
    )
