"""Tests for document ingestion and lifecycle."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from uniassist.core.hashing import sha256_hex
from uniassist.documents.ingestion import DocumentIngestionService, IngestRequest
from uniassist.documents.models import DocumentStatus, SourceType, VerificationState
from uniassist.documents.store import JsonDocumentStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def service(tmp_path: Path) -> DocumentIngestionService:
    store = JsonDocumentStore(
        raw_dir=tmp_path / "raw",
        index_path=tmp_path / "metadata" / "documents.json",
    )
    return DocumentIngestionService(store)


def test_sha256_is_recorded(service: DocumentIngestionService) -> None:
    content = (FIXTURES / "sample.pdf").read_bytes()
    result = service.ingest_bytes(
        filename="sample.pdf",
        content=content,
        request=IngestRequest(title="Rules", source="Registrar"),
    )
    assert result.record.sha256 == sha256_hex(content)


def test_duplicate_content_returns_existing_record(
    service: DocumentIngestionService,
) -> None:
    request = IngestRequest(title="Rules", source="Registrar")
    first = service.ingest_file(FIXTURES / "sample.pdf", request)
    second = service.ingest_file(FIXTURES / "sample.pdf", request)
    assert second.duplicate is True
    assert first.record.document_id == second.record.document_id


def test_different_content_creates_separate_records(
    service: DocumentIngestionService,
) -> None:
    first = service.ingest_file(
        FIXTURES / "sample.pdf",
        IngestRequest(title="PDF", source="Registrar"),
    )
    second = service.ingest_file(
        FIXTURES / "sample.txt",
        IngestRequest(title="TXT", source="Registrar"),
    )
    assert first.record.document_id != second.record.document_id


def test_provenance_fields_are_persisted(service: DocumentIngestionService) -> None:
    result = service.ingest_file(
        FIXTURES / "sample.pdf",
        IngestRequest(
            title="Admission Rules",
            source="SUSU regulations office",
            source_url="https://example.org/rules.pdf",
            effective_date=date(2025, 9, 1),
            version="2025-1",
            notes="Uploaded by admin",
        ),
    )
    record = result.record
    assert record.source == "SUSU regulations office"
    assert record.source_url == "https://example.org/rules.pdf"
    assert record.source_type == SourceType.ADMIN_UPLOAD
    assert record.effective_date == date(2025, 9, 1)
    assert record.version == "2025-1"
    assert record.notes == "Uploaded by admin"


def test_default_draft_status(service: DocumentIngestionService) -> None:
    result = service.ingest_file(
        FIXTURES / "sample.pdf",
        IngestRequest(title="Rules", source="Registrar"),
    )
    assert result.record.status == DocumentStatus.DRAFT


def test_default_pending_verification(service: DocumentIngestionService) -> None:
    result = service.ingest_file(
        FIXTURES / "sample.pdf",
        IngestRequest(title="Rules", source="Registrar"),
    )
    assert result.record.verification_state == VerificationState.PENDING


def test_explicit_activation(service: DocumentIngestionService) -> None:
    uploaded = service.ingest_file(
        FIXTURES / "sample.pdf",
        IngestRequest(title="Rules", source="Registrar"),
    )
    activated = service.activate(uploaded.record.document_id)
    assert activated.status == DocumentStatus.ACTIVE
    assert activated.verification_state == VerificationState.VERIFIED


def test_non_admin_source_type_rejected(service: DocumentIngestionService) -> None:
    with pytest.raises(ValueError, match="admin_upload"):
        service.ingest_bytes(
            filename="sample.pdf",
            content=(FIXTURES / "sample.pdf").read_bytes(),
            request=IngestRequest(
                title="Rules",
                source="ScrapeAI",
                source_type=SourceType.SCRAPEAI,
            ),
        )
