"""Tests for upload validation."""

from __future__ import annotations

from pathlib import Path

from uniassist.documents.validation import (
    DEFAULT_MAX_FILE_SIZE_BYTES,
    validate_upload,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_pdf_validation_accepts_valid_pdf() -> None:
    content = (FIXTURES / "sample.pdf").read_bytes()
    result = validate_upload("report.pdf", content)
    assert result.success is True
    assert result.content_type == "application/pdf"


def test_docx_validation_accepts_valid_docx() -> None:
    content = (FIXTURES / "sample.docx").read_bytes()
    result = validate_upload("rules.docx", content)
    assert result.success is True
    assert (
        result.content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def test_txt_validation_accepts_valid_txt() -> None:
    content = (FIXTURES / "sample.txt").read_bytes()
    result = validate_upload("notes.txt", content)
    assert result.success is True
    assert result.content_type == "text/plain"


def test_unsupported_file_rejected() -> None:
    result = validate_upload("image.png", b"\x89PNG\r\n")
    assert result.success is False
    assert any("unsupported" in error for error in result.errors)


def test_empty_file_rejected() -> None:
    result = validate_upload("empty.pdf", b"")
    assert result.success is False
    assert any("empty" in error for error in result.errors)


def test_maximum_file_size_enforced() -> None:
    content = b"%PDF-" + (b"0" * (DEFAULT_MAX_FILE_SIZE_BYTES + 1))
    result = validate_upload("large.pdf", content, max_size_bytes=1024)
    assert result.success is False
    assert any("maximum size" in error for error in result.errors)
