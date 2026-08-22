"""Tests for link extraction and document candidate discovery."""

from __future__ import annotations

from uniassist.scrapeai.discovery import (
    create_document_candidate,
    detect_content_type,
    extract_links,
    identify_document_candidates,
    is_document_url,
    is_pdf_url,
)
from uniassist.scrapeai.models import LinkCandidate

from .conftest import SAMPLE_HTML


def test_extract_links_from_html() -> None:
    links = extract_links(SAMPLE_HTML, "https://example.org/")
    urls = {link.url for link in links}
    assert "https://example.org/docs/report.pdf" in urls
    assert "https://example.org/about" in urls
    assert "https://other.example.org/external.pdf" in urls


def test_pdf_detection() -> None:
    assert is_pdf_url("https://example.org/files/report.pdf") is True
    assert is_pdf_url("https://example.org/about") is False


def test_document_url_detection() -> None:
    assert is_document_url("https://example.org/file.docx") is True
    assert is_document_url("https://example.org/page.html") is False


def test_content_type_detection_from_header_and_url() -> None:
    assert (
        detect_content_type(
            "https://example.org/file",
            "application/pdf; charset=utf-8",
        )
        == "application/pdf"
    )
    assert (
        detect_content_type("https://example.org/report.pdf", None)
        == "application/pdf"
    )


def test_identify_document_candidates_filters_by_allowed_types() -> None:
    links = [
        LinkCandidate(
            url="https://example.org/report.pdf",
            source_url="https://example.org/",
        ),
        LinkCandidate(
            url="https://example.org/about",
            source_url="https://example.org/",
        ),
    ]
    documents = identify_document_candidates(links, ["application/pdf"])
    assert len(documents) == 1
    assert documents[0].url.endswith("report.pdf")


def test_create_document_candidate_normalizes_fields() -> None:
    candidate = create_document_candidate(
        "https://example.org/docs/report.pdf",
        source_url="https://example.org/",
    )
    assert candidate.content_type == "application/pdf"
    assert candidate.filename == "report.pdf"
