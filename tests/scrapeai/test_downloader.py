"""Tests for the document downloader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from uniassist.scrapeai.downloader import DocumentDownloader
from uniassist.scrapeai.models import DocumentCandidate
from uniassist.scrapeai.storage import DocumentStorage


@dataclass
class FakeResponse:
    url: str
    status: int
    body: bytes
    headers: dict[str, list[bytes]]


def test_downloader_stores_document(tmp_path: Path) -> None:
    storage = DocumentStorage(tmp_path)
    downloader = DocumentDownloader(storage)
    candidate = DocumentCandidate(
        url="https://example.org/report.pdf",
        source_url="https://example.org/",
        content_type="application/pdf",
        filename="report.pdf",
    )
    response = FakeResponse(
        url="https://example.org/report.pdf",
        status=200,
        body=b"%PDF-1.4",
        headers={
            b"Content-Type": [b"application/pdf"],
            b"Content-Length": [b"8"],
        },
    )

    result = downloader.process_response(candidate, response)

    assert result.success is True
    assert result.metadata is not None
    assert result.metadata.local_path.exists()
    assert result.metadata.http_status == 200
    assert result.metadata.content_type == "application/pdf"


def test_duplicate_download_is_skipped(tmp_path: Path) -> None:
    storage = DocumentStorage(tmp_path)
    downloader = DocumentDownloader(storage)
    candidate = DocumentCandidate(
        url="https://example.org/report.pdf",
        source_url="https://example.org/",
        content_type="application/pdf",
        filename="report.pdf",
    )
    response = FakeResponse(
        url="https://example.org/report.pdf",
        status=200,
        body=b"%PDF-duplicate",
        headers={b"Content-Type": [b"application/pdf"]},
    )

    first = downloader.process_response(candidate, response)
    second = downloader.process_response(candidate, response)

    assert first.skipped_duplicate is False
    assert second.skipped_duplicate is True
    assert first.metadata is not None
    assert second.metadata is not None
    assert first.metadata.local_path == second.metadata.local_path


def test_downloader_handles_http_failure(tmp_path: Path) -> None:
    storage = DocumentStorage(tmp_path)
    downloader = DocumentDownloader(storage)
    candidate = DocumentCandidate(
        url="https://example.org/missing.pdf",
        source_url="https://example.org/",
    )
    response = FakeResponse(
        url="https://example.org/missing.pdf",
        status=404,
        body=b"not found",
        headers={},
    )

    result = downloader.process_response(candidate, response)

    assert result.success is False
    assert result.metadata is None
    assert result.error is not None
