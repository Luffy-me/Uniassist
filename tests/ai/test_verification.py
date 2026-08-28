"""Tests for verification engine."""

from __future__ import annotations

from datetime import UTC, datetime

from tests.ai.conftest import LEAVE_TEXT, make_active_record, make_evidence
from uniassist.ai.models import (
    AnswerClaim,
    CandidateAnswer,
    Question,
    RefusalReason,
)
from uniassist.documents.models import DocumentStatus, VerificationState


def test_supported_claim_passes_verification(ai_stack) -> None:
    make_active_record(
        ai_stack["document_store"],
        document_id="doc-1",
        title="Academic Leave Regulations",
    )
    evidence = [
        make_evidence(
            chunk_id="chunk-1",
            document_id="doc-1",
            title="Academic Leave Regulations",
            text=LEAVE_TEXT,
        )
    ]
    candidate = CandidateAnswer(
        answer_text="Students may request academic leave.",
        claims=(
            AnswerClaim(
                text="Students may request academic leave.",
                evidence_ids=("chunk-1",),
            ),
        ),
        evidence=tuple(evidence),
        model="mock",
        generated_at=datetime.now(UTC),
    )
    result = ai_stack["verification"].verify(
        Question(text="Can I take academic leave?"),
        candidate,
        evidence,
    )
    assert result.verified is True
    assert result.supported_claims


def test_one_chunk_can_support_multiple_claims_and_citations_deduplicate(
    ai_stack,
) -> None:
    make_active_record(
        ai_stack["document_store"],
        document_id="doc-1",
        title="Academic Leave Regulations",
    )
    evidence = [
        make_evidence(
            chunk_id="chunk-1",
            document_id="doc-1",
            title="Academic Leave Regulations",
            text=(
                "Students may request academic leave. Students must submit "
                "a formal request to the academic office."
            ),
        )
    ]
    candidate = CandidateAnswer(
        answer_text=(
            "Students may request academic leave. A formal request must be "
            "submitted to the academic office."
        ),
        claims=(
            AnswerClaim(
                text="Students may request academic leave.",
                evidence_ids=("chunk-1",),
            ),
            AnswerClaim(
                text="A formal request must be submitted to the academic office.",
                evidence_ids=("chunk-1",),
            ),
        ),
        evidence=tuple(evidence),
        model="mock",
        generated_at=datetime.now(UTC),
    )
    result = ai_stack["verification"].verify(
        Question(text="How do I request academic leave?"), candidate, evidence
    )
    assert result.verified is True
    assert len(result.supported_claims) == 2
    citations = ai_stack["verification"].build_citations(candidate, evidence)
    assert [citation.chunk_id for citation in citations] == ["chunk-1"]


def test_one_chunk_can_support_three_claims(ai_stack) -> None:
    make_active_record(
        ai_stack["document_store"],
        document_id="doc-1",
        title="Academic Leave Regulations",
    )
    evidence = [
        make_evidence(
            chunk_id="chunk-1",
            document_id="doc-1",
            title="Academic Leave Regulations",
            text=(
                "Students may request academic leave. A formal request is "
                "required. Submit the request to the academic office."
            ),
        )
    ]
    candidate = CandidateAnswer(
        answer_text=(
            "Students may request leave, file a formal request, and submit it "
            "to the academic office."
        ),
        claims=(
            AnswerClaim("Students may request academic leave.", ("chunk-1",)),
            AnswerClaim("A formal request is required.", ("chunk-1",)),
            AnswerClaim("Submit the request to the academic office.", ("chunk-1",)),
        ),
        evidence=tuple(evidence),
        model="mock",
        generated_at=datetime.now(UTC),
    )
    result = ai_stack["verification"].verify(
        Question(text="How do I request academic leave?"), candidate, evidence
    )
    assert result.verified is True
    assert len(result.supported_claims) == 3


def test_duplicate_evidence_in_one_claim_fails_verification(ai_stack) -> None:
    make_active_record(
        ai_stack["document_store"], document_id="doc-1", title="Leave"
    )
    evidence = [
        make_evidence(
            chunk_id="chunk-1",
            document_id="doc-1",
            title="Leave",
            text=LEAVE_TEXT,
        )
    ]
    candidate = CandidateAnswer(
        answer_text="Students may request academic leave.",
        claims=(
            AnswerClaim(
                "Students may request academic leave.",
                ("chunk-1", "chunk-1"),
            ),
        ),
        evidence=tuple(evidence),
        model="mock",
        generated_at=datetime.now(UTC),
    )
    result = ai_stack["verification"].verify(
        Question(text="Can I take academic leave?"), candidate, evidence
    )
    assert result.verified is False
    assert result.refusal_reason == RefusalReason.INVALID_CITATION


def test_unsupported_claim_fails_verification(ai_stack) -> None:
    make_active_record(
        ai_stack["document_store"],
        document_id="doc-1",
        title="Academic Leave Regulations",
    )
    evidence = [
        make_evidence(
            chunk_id="chunk-1",
            document_id="doc-1",
            title="Academic Leave Regulations",
            text=LEAVE_TEXT,
        )
    ]
    candidate = CandidateAnswer(
        answer_text="The maximum duration is ten years.",
        claims=(
            AnswerClaim(
                text="The maximum duration is ten years.",
                evidence_ids=("chunk-1",),
            ),
        ),
        evidence=tuple(evidence),
        model="mock",
        generated_at=datetime.now(UTC),
    )
    result = ai_stack["verification"].verify(
        Question(text="How long?"),
        candidate,
        evidence,
    )
    assert result.verified is False
    assert result.refusal_reason == RefusalReason.UNSUPPORTED_CLAIM


def test_invalid_citation_is_detected(ai_stack) -> None:
    make_active_record(
        ai_stack["document_store"],
        document_id="doc-1",
        title="Academic Leave Regulations",
    )
    evidence = [
        make_evidence(
            chunk_id="chunk-1",
            document_id="doc-1",
            title="Academic Leave Regulations",
            text=LEAVE_TEXT,
        )
    ]
    candidate = CandidateAnswer(
        answer_text="Students may request academic leave.",
        claims=(
            AnswerClaim(
                text="Students may request academic leave.",
                evidence_ids=("missing-chunk",),
            ),
        ),
        evidence=tuple(evidence),
        model="mock",
        generated_at=datetime.now(UTC),
    )
    result = ai_stack["verification"].verify(
        Question(text="Can I take academic leave?"),
        candidate,
        evidence,
    )
    assert result.verified is False
    assert result.refusal_reason == RefusalReason.INVALID_CITATION


def test_inactive_document_is_excluded(ai_stack) -> None:
    make_active_record(
        ai_stack["document_store"],
        document_id="doc-draft",
        title="Draft Rules",
        status=DocumentStatus.DRAFT,
        verification_state=VerificationState.PENDING,
    )
    evidence = [
        make_evidence(
            chunk_id="chunk-draft",
            document_id="doc-draft",
            title="Draft Rules",
            text=LEAVE_TEXT,
        )
    ]
    candidate = CandidateAnswer(
        answer_text="Students may request academic leave.",
        claims=(
            AnswerClaim(
                text="Students may request academic leave.",
                evidence_ids=("chunk-draft",),
            ),
        ),
        evidence=tuple(evidence),
        model="mock",
        generated_at=datetime.now(UTC),
    )
    result = ai_stack["verification"].verify(
        Question(text="Can I take academic leave?"),
        candidate,
        evidence,
    )
    assert result.verified is False


def test_contradictory_duration_evidence_is_detected(ai_stack) -> None:
    make_active_record(
        ai_stack["document_store"],
        document_id="doc-v1",
        title="Leave v1",
        version="v1",
    )
    make_active_record(
        ai_stack["document_store"],
        document_id="doc-v2",
        title="Leave v2",
        version="v2",
    )
    evidence = [
        make_evidence(
            chunk_id="c1",
            document_id="doc-v1",
            title="Leave v1",
            text="Academic leave may be granted for 6 months.",
            version="v1",
        ),
        make_evidence(
            chunk_id="c2",
            document_id="doc-v2",
            title="Leave v2",
            text="Academic leave may be granted for 12 months.",
            version="v2",
        ),
    ]
    candidate = CandidateAnswer(
        answer_text="Academic leave may be granted for 12 months.",
        claims=(
            AnswerClaim(
                text="Academic leave may be granted for 12 months.",
                evidence_ids=("c2",),
            ),
        ),
        evidence=tuple(evidence),
        model="mock",
        generated_at=datetime.now(UTC),
    )
    result = ai_stack["verification"].verify(
        Question(text="How long is academic leave?"),
        candidate,
        evidence,
    )
    assert result.verified is False
    assert result.refusal_reason == RefusalReason.CONTRADICTORY_EVIDENCE
