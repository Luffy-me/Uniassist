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
