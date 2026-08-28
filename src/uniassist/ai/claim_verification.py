"""Layered claim verification models and semantic support checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from uniassist.ai.models import AnswerClaim, EvidenceItem, Question

_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "is",
    "are",
    "may",
    "be",
    "by",
    "with",
    "as",
    "at",
    "it",
    "this",
    "that",
    "their",
    "students",
    "student",
    "university",
}


class ClaimSupportStatus(StrEnum):
    """Precise internal support classification for a claim."""

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClaimAssessment:
    """Structured assessment for one claim."""

    claim_text: str
    status: ClaimSupportStatus
    reason: str = ""
    confidence: float | None = None


class SemanticVerifier(Protocol):
    """Verify whether evidence semantically supports a claim."""

    def verify_claim(
        self,
        question: Question,
        claim: AnswerClaim,
        evidence_items: list[EvidenceItem],
    ) -> ClaimAssessment:
        """Return semantic support assessment for one claim."""


class DeterministicSemanticVerifier:
    """Offline semantic verifier using layered keyword overlap."""

    def verify_claim(
        self,
        question: Question,
        claim: AnswerClaim,
        evidence_items: list[EvidenceItem],
    ) -> ClaimAssessment:
        del question
        if not evidence_items:
            return ClaimAssessment(
                claim_text=claim.text,
                status=ClaimSupportStatus.UNSUPPORTED,
                reason="no evidence provided",
            )
        scores = [
            _keyword_overlap_score(claim.text, item.text)
            for item in evidence_items
        ]
        best = max(scores)
        if best >= 0.5:
            return ClaimAssessment(
                claim_text=claim.text,
                status=ClaimSupportStatus.SUPPORTED,
                reason="keyword overlap supports claim",
                confidence=best,
            )
        if best >= 0.25:
            return ClaimAssessment(
                claim_text=claim.text,
                status=ClaimSupportStatus.PARTIALLY_SUPPORTED,
                reason="partial keyword overlap",
                confidence=best,
            )
        return ClaimAssessment(
            claim_text=claim.text,
            status=ClaimSupportStatus.UNSUPPORTED,
            reason="evidence does not support claim",
            confidence=best,
        )


def _keyword_overlap_score(claim_text: str, evidence_text: str) -> float:
    claim_terms = _keywords(claim_text)
    evidence_terms = _keywords(evidence_text)
    if not claim_terms:
        return 0.0
    overlap = claim_terms & evidence_terms
    return len(overlap) / len(claim_terms)


def _keywords(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {token for token in tokens if token not in _STOPWORDS and len(token) > 2}
