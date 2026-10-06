"""Regression tests: Cyrillic support, figures and negation in verification."""

from __future__ import annotations

from uniassist.ai.claim_verification import (
    ClaimSupportStatus,
    DeterministicSemanticVerifier,
)
from uniassist.ai.models import AnswerClaim, EvidenceItem, Question
from uniassist.core.text import conflicting_durations, keywords, numbers
from uniassist.rag.retrieval import _retrieval_terms


def _evidence(text: str) -> EvidenceItem:
    return EvidenceItem(
        chunk_id="c1",
        document_id="d1",
        title="Regulation",
        text=text,
        page_number=1,
        section=None,
        source="test",
        source_url=None,
        document_version=None,
        source_sha256=None,
        effective_date=None,
        similarity_score=1.0,
    )


def _assess(claim: str, evidence: str):
    return DeterministicSemanticVerifier().verify_claim(
        Question(text="q"),
        AnswerClaim(text=claim, evidence_ids=("c1",)),
        [_evidence(evidence)],
    ).status


def test_cyrillic_claims_are_supported() -> None:
    status = _assess(
        "Академический отпуск предоставляется на один год",
        "Академический отпуск предоставляется студенту на один год по заявлению.",
    )
    assert status == ClaimSupportStatus.SUPPORTED


def test_cyrillic_keywords_and_query_terms() -> None:
    assert "отпуск" in keywords("Академический отпуск")
    assert "отпуск" in _retrieval_terms("Как получить отпуск?")


def test_wrong_figure_is_not_supported() -> None:
    status = _assess(
        "The deadline is 30 days after enrolment",
        "The deadline is 15 days after enrolment.",
    )
    assert status != ClaimSupportStatus.SUPPORTED


def test_matching_figure_is_supported() -> None:
    status = _assess(
        "The deadline is 15 days after enrolment",
        "The deadline is 15 days after enrolment.",
    )
    assert status == ClaimSupportStatus.SUPPORTED


def test_negation_mismatch_is_contradicted() -> None:
    status = _assess(
        "Students may retake the exam twice",
        "Students may not retake the exam twice.",
    )
    assert status == ClaimSupportStatus.CONTRADICTED


def test_numbers_normalise_decimal_comma() -> None:
    assert numbers("1,5 years") == numbers("1.5 years")


def test_unrelated_durations_do_not_conflict() -> None:
    items = [
        ("d1", "Academic leave may last up to 2 years."),
        ("d2", "The tuition invoice is payable within 10 days."),
    ]
    assert conflicting_durations(items) == []


def test_same_subject_different_durations_conflict() -> None:
    items = [
        ("d1", "Academic leave may last up to 2 years."),
        ("d2", "Academic leave may last up to 1 years."),
    ]
    assert conflicting_durations(items)
