"""AI answer and verification models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class RefusalReason(StrEnum):
    """Controlled reasons when an answer cannot be verified."""

    NO_RELEVANT_EVIDENCE = "no_relevant_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"
    INVALID_CITATION = "invalid_citation"
    GENERATION_FAILURE = "generation_failure"
    VERIFICATION_FAILURE = "verification_failure"


@dataclass(frozen=True)
class Question:
    """A user question to be answered from evidence."""

    text: str


@dataclass(frozen=True)
class EvidenceItem:
    """Structured evidence passed to the LLM provider."""

    chunk_id: str
    document_id: str
    title: str
    text: str
    page_number: int | None
    section: str | None
    source: str
    source_url: str | None
    document_version: str | None
    source_sha256: str | None
    effective_date: str | None
    similarity_score: float

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "title": self.title,
            "text": self.text,
            "page_number": self.page_number,
            "section": self.section,
            "source": self.source,
            "source_url": self.source_url,
            "document_version": self.document_version,
            "source_sha256": self.source_sha256,
            "effective_date": self.effective_date,
            "similarity_score": self.similarity_score,
        }


@dataclass(frozen=True)
class AnswerClaim:
    """A factual claim within a candidate answer."""

    text: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateAnswer:
    """A model-generated answer grounded in retrieved evidence."""

    answer_text: str
    claims: tuple[AnswerClaim, ...]
    evidence: tuple[EvidenceItem, ...]
    model: str
    generated_at: datetime


@dataclass(frozen=True)
class Citation:
    """A provenance citation for a verified answer."""

    chunk_id: str
    document_id: str
    title: str
    page_number: int | None
    section: str | None
    source: str
    source_url: str | None

    def display_label(self) -> str:
        if self.page_number is not None:
            location = f"p. {self.page_number}"
        elif self.section:
            location = f"§{self.section}"
        else:
            location = "page n/a"
        return f"{self.title} — {location}"


@dataclass(frozen=True)
class VerificationResult:
    """Outcome of claim-level answer verification."""

    verified: bool
    confidence: float
    supported_claims: tuple[str, ...] = ()
    unsupported_claims: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    citation_errors: tuple[str, ...] = ()
    reasoning_summary: str = ""
    refusal_reason: RefusalReason | None = None
    claim_assessments: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifiedAnswer:
    """A verified answer with citations."""

    answer_text: str
    citations: tuple[Citation, ...]
    verification_result: VerificationResult
    model: str
    generated_at: datetime


@dataclass(frozen=True)
class RefusalAnswer:
    """A controlled response when verification fails."""

    reason: RefusalReason
    message: str
    verification_result: VerificationResult
    model: str | None = None
    generated_at: datetime | None = None


@dataclass(frozen=True)
class PipelineTimings:
    """Safe timing metadata for the answer pipeline."""

    retrieval_latency_ms: float = 0.0
    generation_latency_ms: float = 0.0
    verification_latency_ms: float = 0.0
    total_latency_ms: float = 0.0


@dataclass(frozen=True)
class StructuredAnswerPayload:
    """Parsed structured model output."""

    answer: str
    claims: list[AnswerClaim] = field(default_factory=list)
    insufficient_evidence: bool = False
