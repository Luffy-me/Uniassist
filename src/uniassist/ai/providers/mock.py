"""Deterministic mock LLM provider for offline tests."""

from __future__ import annotations

from datetime import UTC, datetime

from uniassist.ai.models import (
    AnswerClaim,
    CandidateAnswer,
    EvidenceItem,
    Question,
    RefusalReason,
    VerificationResult,
)


class MockLLMProvider:
    """Configurable provider for deterministic unit and integration tests."""

    def __init__(
        self,
        *,
        model_name: str = "mock-llm",
        answer_text: str | None = None,
        claims: list[AnswerClaim] | None = None,
        insufficient_evidence: bool = False,
        verification_verified: bool | None = None,
        raise_on_generate: Exception | None = None,
    ) -> None:
        self._model_name = model_name
        self._answer_text = answer_text
        self._claims = claims
        self._insufficient_evidence = insufficient_evidence
        self._verification_verified = verification_verified
        self._raise_on_generate = raise_on_generate
        self.last_question: Question | None = None
        self.last_evidence: list[EvidenceItem] | None = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate_answer(
        self,
        question: Question,
        evidence: list[EvidenceItem],
    ) -> CandidateAnswer:
        if self._raise_on_generate is not None:
            raise self._raise_on_generate
        self.last_question = question
        self.last_evidence = evidence
        if self._insufficient_evidence:
            return CandidateAnswer(
                answer_text=(
                    "The available documents do not contain sufficient evidence "
                    "to answer this question reliably."
                ),
                claims=(),
                evidence=tuple(evidence),
                model=self._model_name,
                generated_at=datetime.now(UTC),
            )

        if self._claims is not None:
            claims = tuple(self._claims)
        elif evidence:
            claims = (
                AnswerClaim(
                    text=evidence[0].text,
                    evidence_ids=(evidence[0].chunk_id,),
                ),
            )
        else:
            claims = ()

        answer_text = self._answer_text
        if answer_text is None:
            answer_text = (
                evidence[0].text
                if evidence
                else (
                    "Students may request academic leave under the conditions "
                    "specified in the regulation."
                )
            )

        return CandidateAnswer(
            answer_text=answer_text,
            claims=claims,
            evidence=tuple(evidence),
            model=self._model_name,
            generated_at=datetime.now(UTC),
        )

    def verify_answer(
        self,
        question: Question,
        candidate: CandidateAnswer,
        evidence: list[EvidenceItem],
    ) -> VerificationResult:
        del question
        if self._verification_verified is not None:
            verified = self._verification_verified
        else:
            verified = bool(candidate.claims) and all(
                claim.evidence_ids for claim in candidate.claims
            )
        unsupported = tuple(
            claim.text
            for claim in candidate.claims
            if not claim.evidence_ids
        )
        return VerificationResult(
            verified=verified and not unsupported,
            confidence=0.9 if verified else 0.2,
            supported_claims=tuple(
                claim.text for claim in candidate.claims if claim.evidence_ids
            ),
            unsupported_claims=unsupported,
            contradictions=(),
            citation_errors=(),
            reasoning_summary="mock verification",
            refusal_reason=(
                RefusalReason.UNSUPPORTED_CLAIM if unsupported else None
            ),
        )
