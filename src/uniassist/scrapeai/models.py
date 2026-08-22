"""Generic data models for the ScrapeAI acquisition engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from uniassist.scrapeai.config import SourceProfile


@dataclass(frozen=True)
class Source:
    """A named data source backed by a configuration profile."""

    name: str
    profile: SourceProfile


@dataclass(frozen=True)
class LinkCandidate:
    """A hyperlink discovered on a crawled page."""

    url: str
    source_url: str
    text: str = ""


@dataclass(frozen=True)
class DocumentCandidate:
    """A URL that may point to a downloadable document."""

    url: str
    source_url: str
    content_type: str | None = None
    filename: str | None = None


@dataclass(frozen=True)
class DocumentMetadata:
    """Metadata captured when a document is downloaded."""

    source_url: str
    final_url: str
    filename: str
    content_type: str | None
    content_length: int | None
    sha256: str
    retrieved_at: datetime
    http_status: int
    local_path: Path


@dataclass(frozen=True)
class DownloadResult:
    """Outcome of a document download attempt."""

    metadata: DocumentMetadata | None
    success: bool
    skipped_duplicate: bool = False
    error: str | None = None
