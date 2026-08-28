"""Tests for structured response parsing."""

from __future__ import annotations

import pytest

from uniassist.ai.parsing import (
    GenerationParseError,
    parse_json_content,
    parse_structured_answer,
)


def test_parse_structured_answer() -> None:
    payload = parse_json_content(
        """
        {
          "answer": "Students may request academic leave.",
          "insufficient_evidence": false,
          "claims": [
            {"text": "Students may request academic leave.", "evidence_ids": ["c1"]}
          ]
        }
        """
    )
    structured = parse_structured_answer(payload)
    assert structured.answer.startswith("Students may request")
    assert structured.claims[0].evidence_ids == ("c1",)


def test_parse_structured_answer_requires_claims_for_grounded_answer() -> None:
    with pytest.raises(GenerationParseError, match="claims are required"):
        parse_structured_answer(
            {
                "answer": "Students may request academic leave.",
                "insufficient_evidence": False,
                "claims": [],
            }
        )


def test_parse_structured_answer_rejects_missing_claims_field() -> None:
    with pytest.raises(GenerationParseError, match="missing required field"):
        parse_structured_answer(
            {
                "answer": "Students may request academic leave.",
                "insufficient_evidence": False,
            }
        )


def test_parse_structured_answer_rejects_unknown_evidence_id() -> None:
    with pytest.raises(GenerationParseError, match="unknown evidence_id"):
        parse_structured_answer(
            {
                "answer": "Students may request academic leave.",
                "insufficient_evidence": False,
                "claims": [
                    {
                        "text": "Students may request academic leave.",
                        "evidence_ids": ["bad"],
                    }
                ],
            },
            allowed_evidence_ids={"c1"},
        )


def test_parse_structured_answer_rejects_empty_claim_evidence() -> None:
    with pytest.raises(GenerationParseError, match="requires at least one"):
        parse_structured_answer(
            {
                "answer": "Students may request academic leave.",
                "insufficient_evidence": False,
                "claims": [
                    {
                        "text": "Students may request academic leave.",
                        "evidence_ids": [],
                    }
                ],
            }
        )


def test_parse_structured_answer_allows_evidence_reuse_across_claims() -> None:
    structured = parse_structured_answer(
        {
            "answer": "Two claims.",
            "insufficient_evidence": False,
            "claims": [
                {"text": "First claim.", "evidence_ids": ["c1"]},
                {"text": "Second claim.", "evidence_ids": ["c1"]},
            ],
        }
    )
    assert len(structured.claims) == 2


def test_parse_structured_answer_rejects_duplicate_evidence_in_one_claim() -> None:
    with pytest.raises(GenerationParseError, match="unique within each claim"):
        parse_structured_answer(
            {
                "answer": "One claim.",
                "insufficient_evidence": False,
                "claims": [
                    {"text": "First claim.", "evidence_ids": ["c1", "c1"]},
                ],
            }
        )


def test_parse_structured_answer_rejects_missing_answer() -> None:
    with pytest.raises(GenerationParseError, match="answer text is required"):
        parse_structured_answer(
            {
                "answer": "",
                "insufficient_evidence": False,
                "claims": [{"text": "A claim.", "evidence_ids": ["c1"]}],
            }
        )


def test_parse_structured_answer_accepts_explicit_insufficient_evidence() -> None:
    structured = parse_structured_answer(
        {
            "answer": "Evidence is insufficient.",
            "insufficient_evidence": True,
            "claims": [],
        }
    )
    assert structured.insufficient_evidence is True
    assert structured.claims == []


def test_parse_structured_answer_rejects_claims_for_insufficient_evidence() -> None:
    with pytest.raises(GenerationParseError, match="must not include claims"):
        parse_structured_answer(
            {
                "answer": "Evidence is insufficient.",
                "insufficient_evidence": True,
                "claims": [{"text": "A claim.", "evidence_ids": ["c1"]}],
            }
        )


def test_prose_surrounding_json_is_extracted() -> None:
    payload = parse_json_content('Here is the answer: {"answer": "x"}')
    assert payload == {"answer": "x"}


def test_reasoning_wrapped_json_is_extracted() -> None:
    payload = parse_json_content('<think>Use evidence.</think>\n{"answer": "x"}')
    assert payload == {"answer": "x"}


def test_malformed_json_raises() -> None:
    with pytest.raises(GenerationParseError, match="valid JSON"):
        parse_json_content("not json")
