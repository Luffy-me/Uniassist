"""Tests for Telegram message formatting."""

from __future__ import annotations

from uniassist.ai.models import Citation
from uniassist.telegram.api_client import AskResult, CitationPayload
from uniassist.telegram.errors import REFUSAL_MESSAGE
from uniassist.telegram.formatting import (
    escape_markdown,
    format_ask_result,
    format_citation,
    split_message,
)


def test_format_verified_answer_with_citations() -> None:
    result = AskResult(
        request_id="r1",
        status="verified",
        answer="Students may request academic leave.",
        citations=(
            CitationPayload(
                chunk_id="c1",
                document_id="d1",
                title="Academic Leave Regulations",
                page_number=4,
                section="2.1",
                source="TEST",
                source_url=None,
                label="Academic Leave Regulations — p. 4",
            ),
        ),
        verified=True,
    )
    text = format_ask_result(result)
    assert "Students may request academic leave." in text
    assert "Sources / Источники:" in text
    assert "Academic Leave Regulations — p. 4" in text


def test_format_refusal_uses_bilingual_student_message() -> None:
    refused = AskResult(
        request_id="r2",
        status="refused",
        message="No relevant evidence.",
        verified=False,
    )
    assert format_ask_result(refused) == REFUSAL_MESSAGE
    assert format_ask_result(
        AskResult(request_id="r3", status="refused", verified=False)
    ) == REFUSAL_MESSAGE


def test_format_citation_without_page_uses_section() -> None:
    citation = CitationPayload(
        chunk_id="c1",
        document_id="d1",
        title="Student Regulations",
        page_number=None,
        section="2.1",
        source="TEST",
        source_url=None,
        label="",
    )
    assert format_citation(citation) == "• Student Regulations — §2.1"


def test_format_citation_includes_official_source_url() -> None:
    citation = CitationPayload(
        chunk_id="c1",
        document_id="d1",
        title="Student Regulations",
        page_number=None,
        section="2.1",
        source="TEST",
        source_url="https://example.org/regulations",
        label="",
    )
    text = format_citation(citation)
    assert "Student Regulations — §2.1" in text
    assert "https://example.org/regulations" in text


def test_citation_label_uses_section_when_page_is_unavailable() -> None:
    citation = Citation(
        chunk_id="c1",
        document_id="d1",
        title="Student Regulations",
        page_number=None,
        section="2.1",
        source="TEST",
        source_url="https://example.org/regulations",
    )
    assert citation.display_label() == "Student Regulations — §2.1"


def test_split_message_prefers_paragraph_boundaries() -> None:
    text = "Paragraph one.\n\nParagraph two is longer and should split safely."
    chunks = split_message(text, max_length=30)
    assert len(chunks) >= 2
    assert "".join(chunks).replace("\n", "").replace(" ", "") != ""


def test_escape_markdown() -> None:
    assert escape_markdown("Title_with*markdown") == "Title\\_with\\*markdown"
