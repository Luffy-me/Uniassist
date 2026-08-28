"""Tests for conservative PDF text extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.processing.conftest import FIXTURES, build_record, make_active_record
from tests.processing.pdf_helpers import write_text_pdf
from uniassist.processing.models import ProcessingStatus
from uniassist.processing.processors.base import ProcessorContext
from uniassist.processing.processors.pdf_text import (
    EmptyPdfTextError,
    PdfTextProcessor,
)


def test_pdf_text_processor_extracts_embedded_text(tmp_path: Path) -> None:
    pdf_path = tmp_path / "leave.pdf"
    write_text_pdf(pdf_path, "Students may request academic leave.")
    record = build_record(
        document_id="pdf-text-1",
        filename="leave.pdf",
        local_path=pdf_path,
        sha256="sha",
    )
    normalized = PdfTextProcessor().process(
        ProcessorContext(
            record=record,
            output_dir=tmp_path / "out",
            input_path=pdf_path,
        )
    )
    assert "academic leave" in normalized.blocks[0].text.lower()
    assert normalized.processor == "pdf_text"


def test_pdf_text_processor_rejects_empty_pdf() -> None:
    record = build_record(
        document_id="empty-pdf",
        filename="sample.pdf",
        local_path=FIXTURES / "sample.pdf",
        sha256="sha",
    )
    with pytest.raises(EmptyPdfTextError, match="no extractable text"):
        PdfTextProcessor().process(
            ProcessorContext(
                record=record,
                output_dir=FIXTURES,
                input_path=FIXTURES / "sample.pdf",
            )
        )


def test_pdf_processing_falls_back_to_embedded_text(
    tmp_corpus,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MINERU_EXECUTABLE", raising=False)
    monkeypatch.setattr(
        "uniassist.processing.processors.mineru.mineru_available",
        lambda: False,
    )
    ingestion, processing = tmp_corpus
    pdf_path = tmp_path / "leave.pdf"
    write_text_pdf(pdf_path, "Students may request academic leave.")
    record = make_active_record(ingestion, pdf_path)
    result = processing.process_document(record.document_id)
    assert result.status == ProcessingStatus.COMPLETED
    assert result.processor == "pdf_text"
    normalized = processing.get_normalized(record.document_id)
    assert normalized is not None
    assert "academic leave" in normalized.blocks[0].text.lower()
