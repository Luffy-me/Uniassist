"""Tests for answer generation service."""

from __future__ import annotations

import pytest

from tests.ai.conftest import LEAVE_TEXT, ingest_process_index
from uniassist.ai.generation import (
    AnswerGenerationService,
    GenerationError,
    GenerationFailure,
)
from uniassist.ai.models import RefusalReason
from uniassist.ai.parsing import GenerationParseError
from uniassist.ai.providers.mock import MockLLMProvider


def test_generation_returns_failure_without_evidence(ai_stack) -> None:
    result = ai_stack["generation"].generate("Can I take academic leave?")
    assert isinstance(result, GenerationFailure)
    assert result.reason == RefusalReason.NO_RELEVANT_EVIDENCE


def test_generation_uses_retrieved_evidence(ai_stack) -> None:
    ingest_process_index(
        ai_stack,
        filename="leave.txt",
        content=LEAVE_TEXT,
        title="Academic Leave Regulations",
    )
    result = ai_stack["generation"].generate("Can I take academic leave?")
    assert not isinstance(result, GenerationFailure)
    assert result.candidate.evidence
    assert ai_stack["provider"].last_evidence is not None


def test_provider_exception_is_wrapped(ai_stack) -> None:
    ingest_process_index(
        ai_stack,
        filename="leave.txt",
        content=LEAVE_TEXT,
        title="Academic Leave Regulations",
    )
    ai_stack["provider"]._raise_on_generate = ValueError("boom")  # noqa: SLF001
    with pytest.raises(GenerationError, match="boom"):
        ai_stack["generation"].generate("Can I take academic leave?")


def test_malformed_provider_response_returns_generation_failure(ai_stack) -> None:
    ingest_process_index(
        ai_stack,
        filename="leave.txt",
        content=LEAVE_TEXT,
        title="Academic Leave Regulations",
    )
    provider = MockLLMProvider(
        raise_on_generate=GenerationParseError("bad json"),
    )
    generation = AnswerGenerationService(ai_stack["retriever"], provider)
    result = generation.generate("Can I take academic leave?")
    assert isinstance(result, GenerationFailure)
    assert result.reason == RefusalReason.GENERATION_FAILURE
