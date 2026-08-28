"""Grounded answer generation service."""

from __future__ import annotations

import time
from dataclasses import dataclass

from uniassist.ai.evidence import evidence_from_retrieved
from uniassist.ai.models import CandidateAnswer, Question, RefusalReason
from uniassist.ai.observability import (
    log_request_end,
    log_request_start,
    new_request_context,
)
from uniassist.ai.parsing import GenerationParseError, InsufficientEvidenceError
from uniassist.ai.providers.base import LLMProvider
from uniassist.rag.retrieval import Retriever


class GenerationError(RuntimeError):
    """Raised when answer generation fails."""


@dataclass(frozen=True)
class GenerationFailure:
    """Controlled generation failure."""

    reason: RefusalReason
    message: str
    retrieval_latency_ms: float = 0.0


@dataclass(frozen=True)
class GenerationSuccess:
    """Successful generation with safe timing metadata."""

    candidate: CandidateAnswer
    retrieval_latency_ms: float = 0.0
    top_score: float | None = None
    potentially_conflicting: bool = False


class AnswerGenerationService:
    """Retrieve evidence and generate a grounded candidate answer."""

    def __init__(
        self,
        retriever: Retriever,
        provider: LLMProvider,
        *,
        top_k: int = 8,
    ) -> None:
        self._retriever = retriever
        self._provider = provider
        self._top_k = top_k

    def generate(
        self,
        question_text: str,
    ) -> GenerationSuccess | GenerationFailure:
        question = Question(text=question_text.strip())
        if not question.text:
            return GenerationFailure(
                reason=RefusalReason.GENERATION_FAILURE,
                message="Question must not be empty.",
            )

        retrieval = self._retriever.retrieve_with_metadata(
            question.text,
            top_k=self._top_k,
        )
        records = {}
        indexing_service = self._retriever._indexing_service  # noqa: SLF001
        if indexing_service is not None:
            records = {
                record.document_id: record
                for record in indexing_service.document_store.list_records()
            }
        evidence = evidence_from_retrieved(retrieval.chunks, records=records)
        if not evidence:
            return GenerationFailure(
                reason=RefusalReason.NO_RELEVANT_EVIDENCE,
                message=(
                    "No relevant evidence was found in the verified document corpus."
                ),
                retrieval_latency_ms=retrieval.retrieval_latency_ms,
            )

        context = new_request_context(
            question.text,
            model=self._provider.model_name,
            chunk_count=len(evidence),
            embedding_model=_embedding_model(self._retriever),
            embedding_dimension=_embedding_dimension(self._retriever),
            top_score=retrieval.top_score,
        )
        log_request_start(context)
        started = time.perf_counter()
        try:
            candidate = self._provider.generate_answer(question, evidence)
        except InsufficientEvidenceError as exc:
            log_request_end(
                context,
                verified=False,
                failure_type=RefusalReason.NO_RELEVANT_EVIDENCE.value,
                generation_latency_ms=(time.perf_counter() - started) * 1000,
            )
            return GenerationFailure(
                reason=RefusalReason.NO_RELEVANT_EVIDENCE,
                message=str(exc),
                retrieval_latency_ms=retrieval.retrieval_latency_ms,
            )
        except GenerationParseError as exc:
            log_request_end(
                context,
                verified=False,
                failure_type=RefusalReason.GENERATION_FAILURE.value,
                generation_latency_ms=(time.perf_counter() - started) * 1000,
            )
            return GenerationFailure(
                reason=RefusalReason.GENERATION_FAILURE,
                message=str(exc),
                retrieval_latency_ms=retrieval.retrieval_latency_ms,
            )
        except Exception as exc:
            log_request_end(
                context,
                verified=False,
                failure_type=type(exc).__name__,
                generation_latency_ms=(time.perf_counter() - started) * 1000,
            )
            raise GenerationError(str(exc)) from exc

        generation_latency_ms = (time.perf_counter() - started) * 1000
        log_request_end(
            context,
            verified=True,
            generation_latency_ms=generation_latency_ms,
        )
        return GenerationSuccess(
            candidate=candidate,
            retrieval_latency_ms=retrieval.retrieval_latency_ms,
            top_score=retrieval.top_score,
            potentially_conflicting=retrieval.potentially_conflicting,
        )


def _embedding_model(retriever: Retriever) -> str | None:
    info = getattr(retriever._embedding_provider, "info", None)  # noqa: SLF001
    if info is not None:
        return info.model_name
    return getattr(retriever._embedding_provider, "provider_name", None)  # noqa: SLF001


def _embedding_dimension(retriever: Retriever) -> int | None:
    return getattr(retriever._embedding_provider, "dimension", None)  # noqa: SLF001
