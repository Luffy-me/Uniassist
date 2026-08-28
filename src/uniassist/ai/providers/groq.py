"""Groq chat provider with schema-constrained JSON responses."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from uniassist.ai.models import (
    CandidateAnswer,
    EvidenceItem,
    Question,
    RefusalReason,
    VerificationResult,
)
from uniassist.ai.parsing import (
    InsufficientEvidenceError,
    extract_message_content,
    parse_json_content,
    parse_structured_answer,
    parse_verification_payload,
)
from uniassist.ai.prompting import (
    build_generation_messages,
    build_verification_messages,
)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_CHAT_MODEL = "openai/gpt-oss-20b"


class GroqConfigError(RuntimeError):
    """Raised when the Groq chat provider is not configured."""


class GroqAPIError(RuntimeError):
    """Raised when Groq cannot complete an API request."""


@dataclass(frozen=True)
class GroqClientConfig:
    """Configuration for Groq's OpenAI-compatible chat API."""

    api_key: str
    model: str = DEFAULT_GROQ_CHAT_MODEL
    base_url: str = GROQ_BASE_URL
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> GroqClientConfig:
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            raise GroqConfigError("GROQ_API_KEY is required when using Groq chat.")
        return cls(
            api_key=api_key,
            model=(
                os.environ.get("GROQ_CHAT_MODEL", "").strip()
                or DEFAULT_GROQ_CHAT_MODEL
            ),
            base_url=(
                os.environ.get("GROQ_BASE_URL", "").strip().rstrip("/")
                or GROQ_BASE_URL
            ),
            timeout_seconds=float(os.environ.get("GROQ_TIMEOUT_SECONDS", "60")),
        )


class GroqClient:
    """Minimal client for Groq chat completions."""

    def __init__(self, config: GroqClientConfig) -> None:
        self._config = config

    @property
    def model(self) -> str:
        return self._config.model

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        schema_name: str = "answer",
        response_format_json: bool = True,
        temperature: float = 0.2,
        max_tokens: int = 700,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if response_format_json:
            payload["response_format"] = _strict_json_schema(schema_name)
        return _request_json(
            url=f"{self._config.base_url}/chat/completions",
            api_key=self._config.api_key,
            timeout_seconds=self._config.timeout_seconds,
            payload=payload,
        )


class GroqProvider:
    """Grounded answer generation and verification via Groq."""

    def __init__(self, client: GroqClient | None = None) -> None:
        self._client = client

    def _require_client(self) -> GroqClient:
        if self._client is None:
            self._client = GroqClient(GroqClientConfig.from_env())
        return self._client

    @property
    def model_name(self) -> str:
        if self._client is None:
            configured = os.environ.get("GROQ_CHAT_MODEL", "").strip()
            return configured or DEFAULT_GROQ_CHAT_MODEL
        return self._client.model

    def generate_answer(
        self,
        question: Question,
        evidence: list[EvidenceItem],
    ) -> CandidateAnswer:
        response = self._require_client().chat_completion(
            build_generation_messages(question, evidence),
            schema_name="answer",
            temperature=0.0,
        )
        structured = parse_structured_answer(
            parse_json_content(extract_message_content(response)),
            allowed_evidence_ids={item.chunk_id for item in evidence},
        )
        if structured.insufficient_evidence:
            raise InsufficientEvidenceError(
                "The available documents do not contain sufficient evidence "
                "to answer this question reliably."
            )
        return CandidateAnswer(
            answer_text=structured.answer,
            claims=tuple(structured.claims),
            evidence=tuple(evidence),
            model=self.model_name,
            generated_at=datetime.now(UTC),
        )

    def verify_answer(
        self,
        question: Question,
        candidate: CandidateAnswer,
        evidence: list[EvidenceItem],
    ) -> VerificationResult:
        response = self._require_client().chat_completion(
            build_verification_messages(question, candidate, evidence),
            schema_name="verification",
        )
        payload = parse_verification_payload(
            parse_json_content(extract_message_content(response))
        )
        refusal = None
        if not payload["verified"]:
            if payload["unsupported_claims"]:
                refusal = RefusalReason.UNSUPPORTED_CLAIM
            elif payload["contradictions"]:
                refusal = RefusalReason.CONTRADICTORY_EVIDENCE
            elif payload["citation_errors"]:
                refusal = RefusalReason.INVALID_CITATION
            else:
                refusal = RefusalReason.VERIFICATION_FAILURE
        return VerificationResult(
            verified=payload["verified"],
            confidence=payload["confidence"],
            supported_claims=payload["supported_claims"],
            unsupported_claims=payload["unsupported_claims"],
            contradictions=payload["contradictions"],
            citation_errors=payload["citation_errors"],
            reasoning_summary=payload["reasoning_summary"],
            refusal_reason=refusal,
        )


def _strict_json_schema(schema_name: str) -> dict[str, Any]:
    """Return the exact response shape required for one pipeline stage."""
    if schema_name == "answer":
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "answer": {"type": "string"},
                "insufficient_evidence": {"type": "boolean"},
                "claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "text": {"type": "string"},
                            "evidence_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["text", "evidence_ids"],
                    },
                },
            },
            "required": ["answer", "insufficient_evidence", "claims"],
        }
    elif schema_name == "verification":
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "verified": {"type": "boolean"},
                "confidence": {"type": "number"},
                "supported_claims": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "unsupported_claims": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "contradictions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "citation_errors": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "reasoning_summary": {"type": "string"},
            },
            "required": [
                "verified",
                "confidence",
                "supported_claims",
                "unsupported_claims",
                "contradictions",
                "citation_errors",
                "reasoning_summary",
            ],
        }
    else:
        raise ValueError(f"Unsupported Groq response schema: {schema_name}")
    return {
        "type": "json_schema",
        "json_schema": {
            "name": f"uniassist_{schema_name}",
            "strict": True,
            "schema": schema,
        },
    }


def _request_json(
    *, url: str, api_key: str, timeout_seconds: float, payload: dict[str, Any]
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "UniAssist/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise GroqAPIError(f"Groq API error {exc.code}: {body[:500]}") from exc
    except (TimeoutError, urllib.error.URLError) as exc:
        raise GroqAPIError(f"Groq API request failed: {exc}") from exc
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise GroqAPIError("Groq API response was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise GroqAPIError("Groq API response was not a JSON object")
    return parsed
