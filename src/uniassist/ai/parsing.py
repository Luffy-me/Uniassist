"""Structured response parsing for LLM providers."""

from __future__ import annotations

import json
import re
from typing import Any

from uniassist.ai.models import AnswerClaim, StructuredAnswerPayload


class GenerationParseError(ValueError):
    """Raised when model output cannot be parsed into structured form."""


class InsufficientEvidenceError(GenerationParseError):
    """Raised when the model explicitly reports insufficient evidence."""


def extract_message_content(response: dict[str, Any]) -> str:
    """Extract assistant message content from a chat completion response."""
    try:
        return str(response["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise GenerationParseError(
            "chat provider response missing message content"
        ) from exc


def parse_json_content(content: str) -> dict[str, Any]:
    """Parse a JSON object from model content, tolerating safe wrappers."""
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        payload = _extract_json_object(cleaned)
        if payload is None:
            raise GenerationParseError("model output is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise GenerationParseError("model output JSON must be an object")
    return payload


def _extract_json_object(content: str) -> dict[str, Any] | None:
    """Return a complete JSON object embedded in model reasoning or prose."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", content):
        try:
            payload, _ = decoder.raw_decode(content[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def parse_structured_answer(
    payload: dict[str, Any],
    *,
    allowed_evidence_ids: set[str] | None = None,
) -> StructuredAnswerPayload:
    """Validate and parse structured answer JSON."""
    required_fields = {"answer", "insufficient_evidence", "claims"}
    missing = required_fields.difference(payload)
    if missing:
        raise GenerationParseError(
            f"model output missing required field(s): {', '.join(sorted(missing))}"
        )

    answer_raw = payload["answer"]
    if not isinstance(answer_raw, str):
        raise GenerationParseError("answer must be a string")
    answer = answer_raw.strip()
    insufficient = payload["insufficient_evidence"]
    if not isinstance(insufficient, bool):
        raise GenerationParseError("insufficient_evidence must be a boolean")
    claims_raw = payload["claims"]
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
        normalized_evidence_ids = tuple(
            str(value).strip() for value in evidence_ids if str(value).strip()
        )
        if not normalized_evidence_ids:
            raise GenerationParseError("each claim requires at least one evidence_id")
        if len(set(normalized_evidence_ids)) != len(normalized_evidence_ids):
            raise GenerationParseError(
                "evidence_ids must be unique within each claim"
            )
        if allowed_evidence_ids is not None:
            invalid_ids = set(normalized_evidence_ids).difference(allowed_evidence_ids)
            if invalid_ids:
                raise GenerationParseError("claim references unknown evidence_id")
        claims.append(
            AnswerClaim(
                text=text,
                evidence_ids=normalized_evidence_ids,
            )
        )

    if not answer and not insufficient:
        raise GenerationParseError(
            "answer text is required unless insufficient_evidence"
        )
    if insufficient:
        if claims:
            raise GenerationParseError(
                "insufficient_evidence responses must not include claims"
            )
    elif not claims:
        raise GenerationParseError("claims are required for a grounded answer")

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
