"""Layered claim verification models and semantic support checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from uniassist.ai.models import AnswerClaim, EvidenceItem, Question
from uniassist.core.text import is_negated, keywords, numbers, overlap, sentences


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
        claim_numbers = numbers(claim.text)
        evidence_numbers: set[str] = set()
        for item in evidence_items:
            evidence_numbers |= numbers(item.text)
        missing = claim_numbers - evidence_numbers
        if missing:
            return ClaimAssessment(
                claim_text=claim.text,
                status=ClaimSupportStatus.UNSUPPORTED,
                reason=f"figures not found in evidence: {sorted(missing)}",
                confidence=0.0,
            )

        scores = [
            _keyword_overlap_score(claim.text, item.text)
            for item in evidence_items
        ]
        best = max(scores)
        if best >= 0.5 and _polarity_conflict(claim.text, evidence_items):
            return ClaimAssessment(
                claim_text=claim.text,
                status=ClaimSupportStatus.CONTRADICTED,
                reason="claim and evidence disagree on negation",
                confidence=best,
            )
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


def _polarity_conflict(claim_text: str, evidence_items: list[EvidenceItem]) -> bool:
    """True when the best-matching evidence sentence has opposite negation."""
    claim_terms = keywords(claim_text)
    best_score = 0.0
    best_sentence = ""
    for item in evidence_items:
        for sentence in sentences(item.text):
            score = overlap(claim_terms, keywords(sentence))
            if score > best_score:
                best_score, best_sentence = score, sentence
    if not best_sentence or best_score < 0.5:
        return False
    return is_negated(claim_text) != is_negated(best_sentence)


def _keyword_overlap_score(claim_text: str, evidence_text: str) -> float:
    return overlap(keywords(claim_text), keywords(evidence_text))
