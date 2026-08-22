"""Tests for processing models."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from uniassist.processing.models import (
    NormalizedBlock,
    NormalizedDocument,
    ProcessingResult,
    ProcessingStatus,
)


def test_processing_result_round_trip() -> None:
    result = ProcessingResult(
        document_id="doc-1",
        status=ProcessingStatus.COMPLETED,
        processor="text",
        input_path=Path("/tmp/input.txt"),
        output_path=Path("/tmp/output.json"),
        processed_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_sha256="abc123",
        content_hash="def456",
        processor_version="1.0.0",
    )
    restored = ProcessingResult.from_dict(result.to_dict())
    assert restored == result


def test_normalized_document_round_trip() -> None:
    normalized = NormalizedDocument(
        document_id="doc-1",
        title="Rules",
        source="Registrar",
        source_url="https://example.org/rules",
        source_sha256="abc123",
        processor="text",
        processor_version="1.0.0",
        processed_at=datetime(2026, 1, 1, tzinfo=UTC),
        blocks=[
            NormalizedBlock(text="Paragraph one", page_number=1, section="paragraph_1"),
        ],
    )
    restored = NormalizedDocument.from_dict(normalized.to_dict())
    assert restored == normalized
