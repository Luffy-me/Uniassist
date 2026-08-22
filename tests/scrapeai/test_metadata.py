"""Tests for metadata creation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from uniassist.scrapeai.metadata import build_metadata


def test_metadata_creation(tmp_path: Path) -> None:
    content = b"%PDF-1.4 sample"
    local_path = tmp_path / "report.pdf"
    local_path.write_bytes(content)
    retrieved_at = datetime(2026, 1, 1, tzinfo=UTC)

    metadata = build_metadata(
        source_url="https://example.org/docs/report.pdf",
        final_url="https://example.org/docs/report.pdf",
        content=content,
        http_status=200,
        local_path=local_path,
        content_type="application/pdf",
        content_length=len(content),
        retrieved_at=retrieved_at,
    )

    assert metadata.source_url.endswith("report.pdf")
    assert metadata.final_url.endswith("report.pdf")
    assert metadata.filename == "report.pdf"
    assert metadata.content_type == "application/pdf"
    assert metadata.content_length == len(content)
    assert metadata.http_status == 200
    assert metadata.retrieved_at == retrieved_at
    assert len(metadata.sha256) == 64
