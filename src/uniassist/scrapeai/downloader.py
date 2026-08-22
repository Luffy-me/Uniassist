"""Document download pipeline for ScrapeAI."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from uniassist.scrapeai.discovery import detect_content_type, filename_from_url
from uniassist.scrapeai.logging import get_logger, log_event
from uniassist.scrapeai.metadata import build_metadata
from uniassist.scrapeai.models import DocumentCandidate, DownloadResult
from uniassist.scrapeai.storage import DocumentStorage

logger = get_logger(__name__)


class HttpResponse(Protocol):
    """Minimal response interface used by the downloader."""

    @property
    def url(self) -> str:
        ...

    @property
    def status(self) -> int:
        ...

    @property
    def body(self) -> bytes:
        ...

    @property
    def headers(self) -> dict[str, list[bytes]]:
        ...


def header_value(response: HttpResponse, name: str) -> str | None:
    """Read the first value for an HTTP header."""
    headers = response.headers
    raw: bytes | str | list[bytes] | None

    if hasattr(headers, "get"):
        raw = headers.get(name.encode()) or headers.get(name)
    else:
        raw = None

    if raw is None:
        return None
    if isinstance(raw, list):
        if not raw:
            return None
        raw = raw[0]
    if isinstance(raw, bytes):
        return raw.decode("latin-1")
    return str(raw)


class DocumentDownloader:
    """Download and store approved document candidates."""

    def __init__(self, storage: DocumentStorage) -> None:
        self._storage = storage

    def process_response(
        self,
        candidate: DocumentCandidate,
        response: HttpResponse,
    ) -> DownloadResult:
        """Store a fetched HTTP response as a downloaded document."""
        if response.status >= 400:
            error = f"HTTP {response.status} for {candidate.url}"
            log_event(
                logger,
                40,
                "download_failed",
                url=candidate.url,
                status=response.status,
            )
            return DownloadResult(metadata=None, success=False, error=error)

        content = response.body
        filename = candidate.filename or filename_from_url(response.url) or "document"
        content_type = detect_content_type(
            response.url,
            header_value(response, "Content-Type"),
        )
        content_length_header = header_value(response, "Content-Length")
        content_length = (
            int(content_length_header) if content_length_header is not None else None
        )

        existing_path = self._storage.path_for_hash(
            self._storage_hash(content)
        )
        skipped_duplicate = existing_path is not None
        local_path = self._storage.store(content, filename)

        metadata = build_metadata(
            source_url=candidate.url,
            final_url=response.url,
            content=content,
            http_status=response.status,
            local_path=local_path,
            content_type=content_type or candidate.content_type,
            content_length=content_length,
            retrieved_at=datetime.now(UTC),
        )
        log_event(
            logger,
            20,
            "download_complete",
            url=candidate.url,
            sha256=metadata.sha256,
            skipped_duplicate=skipped_duplicate,
        )
        return DownloadResult(
            metadata=metadata,
            success=True,
            skipped_duplicate=skipped_duplicate,
        )

    def _storage_hash(self, content: bytes) -> str:
        from uniassist.scrapeai.hashing import sha256_hex

        return sha256_hex(content)
