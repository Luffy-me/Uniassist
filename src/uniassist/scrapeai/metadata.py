"""Document metadata extraction and normalization."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from uniassist.scrapeai.discovery import detect_content_type, filename_from_url
from uniassist.scrapeai.hashing import sha256_hex
from uniassist.scrapeai.models import DocumentMetadata


def build_metadata(
    *,
    source_url: str,
    final_url: str,
    content: bytes,
    http_status: int,
    local_path: Path,
    content_type: str | None = None,
    content_length: int | None = None,
    retrieved_at: datetime | None = None,
) -> DocumentMetadata:
    """Create :class:`DocumentMetadata` from a downloaded response."""
    resolved_type = content_type or detect_content_type(final_url)
    filename = filename_from_url(final_url) or local_path.name
    return DocumentMetadata(
        source_url=source_url,
        final_url=final_url,
        filename=filename,
        content_type=resolved_type,
        content_length=content_length if content_length is not None else len(content),
        sha256=sha256_hex(content),
        retrieved_at=retrieved_at or datetime.now(UTC),
        http_status=http_status,
        local_path=local_path,
    )
