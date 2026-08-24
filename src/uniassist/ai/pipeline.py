"""End-to-end grounded answer pipeline."""

from __future__ import annotations

import time
from pathlib import Path

from uniassist.ai.generation import (
    AnswerGenerationService,
    GenerationFailure,
)
from uniassist.ai.models import (
    PipelineTimings,
    Question,
    RefusalAnswer,
    RefusalReason,
    VerifiedAnswer,
)
from uniassist.ai.providers.base import LLMProvider
from uniassist.ai.providers.nvidia import NVIDIAProvider
from uniassist.ai.verification import VerificationEngine
from uniassist.documents.store import JsonDocumentStore
from uniassist.rag.indexing import IndexingService
from uniassist.rag.retrieval import Retriever


class AnswerPipeline:
    """Retrieve evidence, generate, verify, and return a grounded answer."""

    def __init__(
        self,
        generation_service: AnswerGenerationService,
        verification_engine: VerificationEngine,
        provider: LLMProvider,
    ) -> None:
        self._generation = generation_service
        self._verification = verification_engine
        self._provider = provider

    @classmethod
    def from_indexing(
        cls,
        indexing: IndexingService,
        project_root: Path,
        *,
        provider: LLMProvider | None = None,
        use_nvidia_semantic_verifier: bool = False,
    ) -> AnswerPipeline:
        """Build a pipeline that shares the API indexing service vector store."""
        retriever = Retriever(
            vector_store=indexing.vector_store,
            embedding_provider=indexing.embedding_provider,
            indexing_service=indexing,
            require_eligibility=True,
        )
        resolved_provider = provider or _default_provider()
        generation = AnswerGenerationService(retriever, resolved_provider)
        verification = VerificationEngine(
            indexing.document_store,
            use_nvidia_semantic_verifier=use_nvidia_semantic_verifier,
        )
        return cls(generation, verification, resolved_provider)

    @classmethod
    def default(
        cls,
        project_root: Path | None = None,
        *,
        provider: LLMProvider | None = None,
        use_nvidia_semantic_verifier: bool = False,
    ) -> AnswerPipeline:
        root = project_root or Path.cwd()
        retriever = Retriever.default(project_root=root)
        resolved_provider = provider or _default_provider()
        document_store = JsonDocumentStore(
            raw_dir=root / "data" / "raw",
            index_path=root / "data" / "metadata" / "documents.json",
        )
        generation = AnswerGenerationService(retriever, resolved_provider)
        verification = VerificationEngine(
            document_store,
            use_nvidia_semantic_verifier=use_nvidia_semantic_verifier,
        )
        return cls(generation, verification, resolved_provider)

    def ask(self, question_text: str) -> VerifiedAnswer | RefusalAnswer:
        total_started = time.perf_counter()
        generated = self._generation.generate(question_text)
        if isinstance(generated, GenerationFailure):
            return RefusalAnswer(
                reason=generated.reason,
                message=generated.message,
                verification_result=_failure_result(
                    generated.reason,
                    generated.message,
                ),
                model=self._provider.model_name,
            )

        candidate = generated.candidate
        question = Question(text=question_text.strip())
        evidence = list(candidate.evidence)
        verify_started = time.perf_counter()
        verification = self._verification.verify(question, candidate, evidence)
        verification_latency_ms = (time.perf_counter() - verify_started) * 1000

        if generated.potentially_conflicting and verification.verified:
            verification = _mark_contradictory(verification)

        if not verification.verified:
            repaired = self._verification.repair_candidate(candidate, verification)
            if repaired is not None:
                repaired_verification = self._verification.verify(
                    question,
                    repaired,
                    evidence,
                )
                if repaired_verification.verified:
                    citations = self._verification.build_citations(repaired, evidence)
                    return VerifiedAnswer(
                        answer_text=repaired.answer_text,
                        citations=citations,
                        verification_result=repaired_verification,
                        model=repaired.model,
                        generated_at=repaired.generated_at,
                    )

            return RefusalAnswer(
                reason=(
                    verification.refusal_reason
                    or RefusalReason.VERIFICATION_FAILURE
                ),
                message=_refusal_message(verification.refusal_reason),
                verification_result=verification,
                model=candidate.model,
                generated_at=candidate.generated_at,
            )

        citations = self._verification.build_citations(candidate, evidence)
        timings = PipelineTimings(
            retrieval_latency_ms=generated.retrieval_latency_ms,
            generation_latency_ms=0.0,
            verification_latency_ms=verification_latency_ms,
            total_latency_ms=(time.perf_counter() - total_started) * 1000,
        )
        del timings
        return VerifiedAnswer(
            answer_text=candidate.answer_text,
            citations=citations,
            verification_result=verification,
            model=candidate.model,
            generated_at=candidate.generated_at,
        )


def _default_provider() -> LLMProvider:
    return NVIDIAProvider()


def _failure_result(reason: RefusalReason, message: str):
    from uniassist.ai.models import VerificationResult

    return VerificationResult(
        verified=False,
        confidence=0.0,
        reasoning_summary=message,
        refusal_reason=reason,
    )


def _mark_contradictory(verification):
    from uniassist.ai.models import VerificationResult

    return VerificationResult(
        verified=False,
        confidence=0.0,
        supported_claims=verification.supported_claims,
        unsupported_claims=verification.unsupported_claims,
        contradictions=verification.contradictions
        or ("potentially conflicting evidence versions detected",),
        citation_errors=verification.citation_errors,
        reasoning_summary=(
            "Retrieved evidence may contain unresolved version conflicts."
        ),
        refusal_reason=RefusalReason.CONTRADICTORY_EVIDENCE,
        claim_assessments=verification.claim_assessments,
    )


def _refusal_message(reason: RefusalReason | None) -> str:
    messages = {
        RefusalReason.NO_RELEVANT_EVIDENCE: (
            "The available documents do not contain relevant evidence "
            "to answer this question reliably."
        ),
        RefusalReason.INSUFFICIENT_EVIDENCE: (
            "The available documents do not contain sufficient evidence "
            "to answer this question reliably."
        ),
        RefusalReason.UNSUPPORTED_CLAIM: (
            "The generated answer contains claims that are not supported "
            "by the retrieved evidence."
        ),
        RefusalReason.CONTRADICTORY_EVIDENCE: (
            "The retrieved evidence contains conflicting statements that "
            "cannot be resolved safely."
        ),
        RefusalReason.INVALID_CITATION: (
            "The generated answer cites evidence that is missing or ineligible."
        ),
        RefusalReason.GENERATION_FAILURE: (
            "Answer generation failed due to malformed model output."
        ),
        RefusalReason.VERIFICATION_FAILURE: (
            "The answer could not be verified against the retrieved evidence."
        ),
    }
    if reason is None:
        return messages[RefusalReason.VERIFICATION_FAILURE]
    return messages.get(reason, messages[RefusalReason.VERIFICATION_FAILURE])
