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


def _pipeline_with(ai_stack, provider, *, llm_verification: bool):
    from uniassist.ai.generation import AnswerGenerationService
    from uniassist.ai.pipeline import AnswerPipeline

    generation = AnswerGenerationService(ai_stack["retriever"], provider)
    return AnswerPipeline(
        generation,
        ai_stack["verification"],
        provider,
        llm_verification=llm_verification,
    )


def test_llm_second_opinion_can_veto_an_answer(ai_stack) -> None:
    from uniassist.ai.providers.mock import MockLLMProvider

    ingest_process_index(
        ai_stack,
        filename="leave.txt",
        content=LEAVE_TEXT,
        title="Academic Leave Regulations",
    )
    vetoing = MockLLMProvider(verification_verified=False)
    pipeline = _pipeline_with(ai_stack, vetoing, llm_verification=True)
    assert isinstance(pipeline.ask("Can I take academic leave?"), RefusalAnswer)

    agreeing = MockLLMProvider(verification_verified=True)
    pipeline = _pipeline_with(ai_stack, agreeing, llm_verification=True)
    assert isinstance(pipeline.ask("Can I take academic leave?"), VerifiedAnswer)


def test_llm_second_opinion_fails_closed_on_error(ai_stack) -> None:
    from uniassist.ai.providers.mock import MockLLMProvider

    ingest_process_index(
        ai_stack,
        filename="leave.txt",
        content=LEAVE_TEXT,
        title="Academic Leave Regulations",
    )

    class _Broken(MockLLMProvider):
        def verify_answer(self, *args, **kwargs):
            raise RuntimeError("verifier down")

    pipeline = _pipeline_with(ai_stack, _Broken(), llm_verification=True)
    assert isinstance(pipeline.ask("Can I take academic leave?"), RefusalAnswer)
