"""Tests for document processing service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.processing.conftest import (
    FIXTURES,
    activate_record,
    build_record,
    make_active_record,
)
from uniassist.core.hashing import sha256_hex
from uniassist.documents.ingestion import DocumentIngestionService, IngestRequest
from uniassist.documents.models import DocumentStatus, VerificationState
from uniassist.processing.models import ProcessingStatus
from uniassist.processing.processors.mineru import MinerUNotInstalledError
from uniassist.processing.service import (
    DocumentProcessingService,
    ProcessingEligibilityError,
)
from uniassist.processing.store import ProcessingStore


def test_text_processing_completes(tmp_corpus) -> None:
    ingestion, processing = tmp_corpus
    record = make_active_record(ingestion, FIXTURES / "sample.txt")
    result = processing.process_document(record.document_id)

    assert result.status == ProcessingStatus.COMPLETED
    assert result.processor == "text"
    assert result.output_path is not None
    assert result.processor_version == "1.0.0"
    assert result.content_hash == sha256_hex(result.output_path.read_bytes())


def test_output_location_is_deterministic(tmp_corpus) -> None:
    ingestion, processing = tmp_corpus
    record = make_active_record(ingestion, FIXTURES / "sample.txt")
    result = processing.process_document(record.document_id)

    expected = (
        processing._processing_store.processed_dir  # noqa: SLF001
        / record.document_id
        / record.sha256
        / "normalized.json"
    )
    assert result.output_path == expected


def test_provenance_is_preserved_in_normalized_output(tmp_corpus) -> None:
    ingestion, processing = tmp_corpus
    uploaded = ingestion.ingest_file(
        FIXTURES / "sample.txt",
        IngestRequest(
            title="Admission Rules",
            source="SUSU regulations office",
            source_url="https://example.org/rules.txt",
        ),
    )
    record = activate_record(ingestion, uploaded.record.document_id)
    processing.process_document(record.document_id)
    normalized = processing.get_normalized(record.document_id)

    assert normalized is not None
    assert normalized.document_id == record.document_id
    assert normalized.title == "Admission Rules"
    assert normalized.source == "SUSU regulations office"
    assert normalized.source_url == "https://example.org/rules.txt"
    assert normalized.source_sha256 == record.sha256
    assert normalized.processor == "text"
    assert normalized.blocks[0].text


def test_raw_file_remains_unchanged(tmp_corpus) -> None:
    ingestion, processing = tmp_corpus
    record = make_active_record(ingestion, FIXTURES / "sample.txt")
    before = record.local_path.read_bytes()
    processing.process_document(record.document_id)
    after = record.local_path.read_bytes()
    assert before == after


def test_missing_source_file_fails(tmp_corpus, tmp_path: Path) -> None:
    ingestion, processing = tmp_corpus
    missing_path = tmp_path / "missing.txt"
    record = build_record(
        document_id="missing-1",
        filename="missing.txt",
        local_path=missing_path,
        sha256="deadbeef",
    )
    ingestion._store.add_record(record)  # noqa: SLF001
    result = processing.process_document(record.document_id)

    assert result.status == ProcessingStatus.FAILED
    assert "source file not found" in (result.error or "")


def test_empty_pdf_fails_clearly_without_mineru(
    tmp_corpus,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MINERU_EXECUTABLE", raising=False)
    monkeypatch.setattr(
        "uniassist.processing.processors.mineru.mineru_available",
        lambda: False,
    )
    ingestion, processing = tmp_corpus
    record = make_active_record(ingestion, FIXTURES / "sample.pdf")
    result = processing.process_document(record.document_id)

    assert result.processor == "pdf_text"
    assert result.status == ProcessingStatus.FAILED
    assert result.error is not None
    assert "no extractable text" in result.error
    assert "Install MinerU" in result.error


def test_pdf_processing_succeeds_with_mocked_mineru(tmp_corpus, tmp_path: Path) -> None:
    ingestion, processing = tmp_corpus
    record = make_active_record(ingestion, FIXTURES / "sample.pdf")

    def fake_run_mineru(input_path: Path, output_dir: Path, **kwargs):
        mineru_dir = output_dir / "mineru"
        mineru_dir.mkdir(parents=True, exist_ok=True)
        (mineru_dir / "page_1.md").write_text("Extracted PDF text", encoding="utf-8")
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = ""
        completed.stderr = ""
        return completed

    with (
        patch(
            "uniassist.processing.processors.mineru.mineru_available",
            return_value=True,
        ),
        patch(
            "uniassist.processing.processors.mineru.run_mineru",
            side_effect=fake_run_mineru,
        ),
    ):
        result = processing.process_document(record.document_id)

    assert result.status == ProcessingStatus.COMPLETED
    assert result.processor == "mineru"
    normalized = processing.get_normalized(record.document_id)
    assert normalized is not None
    assert normalized.blocks[0].text == "Extracted PDF text"


def test_failed_mineru_preserves_raw_file(tmp_corpus) -> None:
    ingestion, processing = tmp_corpus
    record = make_active_record(ingestion, FIXTURES / "sample.pdf")
    before = record.local_path.read_bytes()

    with (
        patch(
            "uniassist.processing.processors.mineru.mineru_available",
            return_value=True,
        ),
        patch(
            "uniassist.processing.processors.mineru.run_mineru",
            side_effect=RuntimeError("MinerU exploded"),
        ),
    ):
        result = processing.process_document(record.document_id)

    assert result.status == ProcessingStatus.FAILED
    assert record.local_path.read_bytes() == before


def test_docx_is_unsupported_when_mineru_unavailable(
    tmp_corpus,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MINERU_EXECUTABLE", raising=False)
    monkeypatch.setattr(
        "uniassist.processing.processors.mineru.mineru_cli_path",
        lambda: None,
    )
    ingestion, processing = tmp_corpus
    docx_path = tmp_path / "sample.docx"
    docx_path.write_bytes(b"PK\x03\x04minimal docx placeholder")
    record = make_active_record(ingestion, docx_path)
    result = processing.process_document(record.document_id)

    assert result.status == ProcessingStatus.UNSUPPORTED
    assert result.processor == "mineru"
    assert "DOCX" in (result.error or "")


def test_eligibility_requires_active_and_verified(tmp_path: Path) -> None:
    from uniassist.documents.store import JsonDocumentStore

    document_store = JsonDocumentStore(
        raw_dir=tmp_path / "raw",
        index_path=tmp_path / "metadata" / "documents.json",
    )
    processing_store = ProcessingStore(
        processed_dir=tmp_path / "processed",
        index_path=tmp_path / "metadata" / "processing.json",
    )
    ingestion = DocumentIngestionService(document_store)
    processing = DocumentProcessingService(
        document_store=document_store,
        processing_store=processing_store,
        require_eligibility=True,
    )
    uploaded = ingestion.ingest_file(
        FIXTURES / "sample.txt",
        IngestRequest(title="Draft", source="Registrar"),
    )
    with pytest.raises(ProcessingEligibilityError, match="ACTIVE"):
        processing.process_document(uploaded.record.document_id)

    activated = ingestion.activate(uploaded.record.document_id)
    assert activated.status == DocumentStatus.ACTIVE
    assert activated.verification_state == VerificationState.VERIFIED
    result = processing.process_document(activated.document_id)
    assert result.status == ProcessingStatus.COMPLETED


def test_unsupported_extension_returns_unsupported_status(
    tmp_corpus,
    tmp_path: Path,
) -> None:
    ingestion, processing = tmp_corpus
    html_path = tmp_path / "page.html"
    html_path.write_text("<html></html>", encoding="utf-8")
    record = build_record(
        document_id="html-1",
        filename="page.html",
        local_path=html_path,
        sha256=sha256_hex(html_path.read_bytes()),
    )
    ingestion._store.add_record(record)  # noqa: SLF001
    result = processing.process_document(record.document_id)
    assert result.status == ProcessingStatus.UNSUPPORTED


def test_processor_version_recorded_for_text(tmp_corpus) -> None:
    ingestion, processing = tmp_corpus
    record = make_active_record(ingestion, FIXTURES / "sample.txt")
    result = processing.process_document(record.document_id)
    normalized = processing.get_normalized(record.document_id)
    assert result.processor_version == "1.0.0"
    assert normalized is not None
    assert normalized.processor_version == "1.0.0"


def test_mineru_not_installed_error_is_clear(tmp_corpus) -> None:
    ingestion, processing = tmp_corpus
    record = make_active_record(ingestion, FIXTURES / "sample.pdf")
    with (
        patch(
            "uniassist.processing.processors.mineru.mineru_available",
            return_value=True,
        ),
        patch(
            "uniassist.processing.processors.mineru.run_mineru",
            side_effect=MinerUNotInstalledError("MinerU is not installed."),
        ),
    ):
        result = processing.process_document(record.document_id)
    assert result.status == ProcessingStatus.FAILED
    assert "MinerU is not installed." in (result.error or "")
    assert "no extractable text" in (result.error or "")
