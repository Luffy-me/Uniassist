"""LLM provider abstractions."""

from __future__ import annotations

from typing import Protocol

from uniassist.ai.models import (
    CandidateAnswer,
    EvidenceItem,
    Question,
    VerificationResult,
)


class LLMProvider(Protocol):
    """Generate and verify grounded answers from evidence."""

    @property
    def model_name(self) -> str:
        """Return the provider model identifier."""

    def generate_answer(
        self,
        question: Question,
        evidence: list[EvidenceItem],
    ) -> CandidateAnswer:
        """Generate a grounded candidate answer."""

    def verify_answer(
        self,
        question: Question,
        candidate: CandidateAnswer,
        evidence: list[EvidenceItem],
    ) -> VerificationResult:
        """Verify a candidate answer against evidence."""
