"""End-to-end grounded answer pipeline."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from uniassist.ai.generation import (
    AnswerGenerationService,
    GenerationFailure,
)
from uniassist.ai.models import (
    CandidateAnswer,
    EvidenceItem,
    Question,
    RefusalAnswer,
    RefusalReason,
    VerificationResult,
    VerifiedAnswer,
)
from uniassist.ai.providers.base import LLMProvider
from uniassist.ai.providers.groq import GroqProvider
from uniassist.ai.verification import VerificationEngine
from uniassist.documents.store import JsonDocumentStore
from uniassist.rag.indexing import IndexingService
from uniassist.rag.retrieval import Retriever

logger = logging.getLogger("uniassist.ai.pipeline")


class AnswerPipeline:
    """Retrieve evidence, generate, verify, and return a grounded answer."""

    def __init__(
        self,
        generation_service: AnswerGenerationService,
        verification_engine: VerificationEngine,
        provider: LLMProvider,
        *,
        llm_verification: bool | None = None,
    ) -> None:
        self._generation = generation_service
        self._verification = verification_engine
        self._provider = provider
        if llm_verification is None:
            llm_verification = _env_flag("UNIASSIST_LLM_VERIFY")
        self._llm_verification = llm_verification

    @classmethod
    def from_indexing(
        cls,
        indexing: IndexingService,
        project_root: Path,
        *,
        provider: LLMProvider | None = None,
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
        verification = VerificationEngine(indexing.document_store)
        return cls(generation, verification, resolved_provider)

    @classmethod
    def default(
        cls,
        project_root: Path | None = None,
        *,
        provider: LLMProvider | None = None,
    ) -> AnswerPipeline:
        root = project_root or Path.cwd()
        retriever = Retriever.default(project_root=root)
        resolved_provider = provider or _default_provider()
        document_store = JsonDocumentStore(
            raw_dir=root / "data" / "raw",
            index_path=root / "data" / "metadata" / "documents.json",
        )
        generation = AnswerGenerationService(retriever, resolved_provider)
        verification = VerificationEngine(document_store)
        return cls(generation, verification, resolved_provider)

    @property
    def indexing_service(self) -> IndexingService | None:
        return self._generation.retriever.indexing_service

    def _second_opinion(
        self,
        question: Question,
        candidate: CandidateAnswer,
        evidence: list[EvidenceItem],
        verification: VerificationResult,
    ) -> VerificationResult:
        """Optionally require the LLM verifier to agree with the local checks."""
        if not self._llm_verification:
            return verification
        try:
            llm_result = self._provider.verify_answer(question, candidate, evidence)
        except Exception:  # fail closed: an unreachable verifier means no answer
            logger.exception("llm_verification_failed")
            return _failure_result(
                RefusalReason.VERIFICATION_FAILURE,
                "The independent verification step could not be completed.",
            )
        if llm_result.verified:
            return verification
        return llm_result

    def ask(self, question_text: str) -> VerifiedAnswer | RefusalAnswer:
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
        verification = self._verification.verify(question, candidate, evidence)

        if generated.potentially_conflicting and verification.verified:
            verification = _mark_contradictory(verification)

        if verification.verified:
            verification = self._second_opinion(
                question, candidate, evidence, verification
            )

        if not verification.verified:
            repaired = self._verification.repair_candidate(candidate, verification)
            if repaired is not None:
                repaired_verification = self._verification.verify(
                    question,
                    repaired,
                    evidence,
                )
                if repaired_verification.verified:
                    repaired_verification = self._second_opinion(
                        question, repaired, evidence, repaired_verification
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
        return VerifiedAnswer(
            answer_text=candidate.answer_text,
            citations=citations,
            verification_result=verification,
            model=candidate.model,
            generated_at=candidate.generated_at,
        )


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _default_provider() -> LLMProvider:
    return GroqProvider()


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
            "I can't verify an answer to that from the currently available "
            "university documents. Please try a more specific question or "
            "ask the university directly."
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
