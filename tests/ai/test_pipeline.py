"""Tests for end-to-end answer pipeline."""

from __future__ import annotations

from tests.ai.conftest import LEAVE_TEXT, LIBRARY_TEXT, ingest_process_index
from uniassist.ai.models import RefusalAnswer, VerifiedAnswer


def test_pipeline_returns_verified_answer(ai_stack) -> None:
    ingest_process_index(
        ai_stack,
        filename="leave.txt",
        content=LEAVE_TEXT,
        title="Academic Leave Regulations",
    )
    result = ai_stack["pipeline"].ask("Can I take academic leave?")
    assert isinstance(result, VerifiedAnswer)
    assert result.citations
    assert result.verification_result.verified is True


def test_pipeline_refuses_without_evidence(ai_stack) -> None:
    result = ai_stack["pipeline"].ask("Can I take academic leave?")
    assert isinstance(result, RefusalAnswer)
    message = result.message.lower()
    assert "insufficient" in message or "relevant" in message


def test_leave_query_prefers_leave_document(ai_stack) -> None:
    ingest_process_index(
        ai_stack,
        filename="leave.txt",
        content=LEAVE_TEXT,
        title="Academic Leave Regulations",
    )
    ingest_process_index(
        ai_stack,
        filename="library.txt",
        content=LIBRARY_TEXT,
        title="Library Hours",
    )
    result = ai_stack["pipeline"].ask("How can a student request academic leave?")
    assert isinstance(result, VerifiedAnswer)
    assert result.citations[0].title == "Academic Leave Regulations"
