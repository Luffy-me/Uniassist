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
          "claims": [
            {"text": "Students may request academic leave.", "evidence_ids": ["c1"]}
          ]
        }
        """
    )
    structured = parse_structured_answer(payload)
    assert structured.answer.startswith("Students may request")
    assert structured.claims[0].evidence_ids == ("c1",)


def test_malformed_json_raises() -> None:
    with pytest.raises(GenerationParseError, match="valid JSON"):
        parse_json_content("not json")
