"""Structured response parsing for LLM providers."""

from __future__ import annotations

import json
import re
from typing import Any

from uniassist.ai.models import AnswerClaim, StructuredAnswerPayload


class GenerationParseError(ValueError):
    """Raised when model output cannot be parsed into structured form."""


def extract_message_content(response: dict[str, Any]) -> str:
    """Extract assistant message content from a chat completion response."""
    try:
        return str(response["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise GenerationParseError("NVIDIA response missing message content") from exc


def parse_json_content(content: str) -> dict[str, Any]:
    """Parse JSON from model content, tolerating fenced code blocks."""
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise GenerationParseError("model output is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise GenerationParseError("model output JSON must be an object")
    return payload


def parse_structured_answer(payload: dict[str, Any]) -> StructuredAnswerPayload:
    """Validate and parse structured answer JSON."""
    answer = str(payload.get("answer", "")).strip()
    insufficient = bool(payload.get("insufficient_evidence", False))
    claims_raw = payload.get("claims", [])
    if not isinstance(claims_raw, list):
        raise GenerationParseError("claims must be a list")

    claims: list[AnswerClaim] = []
    for item in claims_raw:
        if not isinstance(item, dict):
            raise GenerationParseError("each claim must be an object")
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        evidence_ids = item.get("evidence_ids", [])
        if not isinstance(evidence_ids, list):
            raise GenerationParseError("evidence_ids must be a list")
        claims.append(
            AnswerClaim(
                text=text,
                evidence_ids=tuple(str(value) for value in evidence_ids),
            )
        )

    if not answer and not insufficient:
        raise GenerationParseError(
            "answer text is required unless insufficient_evidence"
        )

    return StructuredAnswerPayload(
        answer=answer,
        claims=claims,
        insufficient_evidence=insufficient,
    )


def parse_verification_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize verification JSON fields."""
    return {
        "verified": bool(payload.get("verified", False)),
        "confidence": float(payload.get("confidence", 0.0)),
        "supported_claims": _as_str_tuple(payload.get("supported_claims", [])),
        "unsupported_claims": _as_str_tuple(payload.get("unsupported_claims", [])),
        "contradictions": _as_str_tuple(payload.get("contradictions", [])),
        "citation_errors": _as_str_tuple(payload.get("citation_errors", [])),
        "reasoning_summary": str(payload.get("reasoning_summary", "")).strip(),
    }


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())
