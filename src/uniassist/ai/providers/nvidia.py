"""NVIDIA LLM provider implementation."""

from __future__ import annotations

from datetime import UTC, datetime

from uniassist.ai.models import (
    CandidateAnswer,
    EvidenceItem,
    Question,
    RefusalReason,
    StructuredAnswerPayload,
    VerificationResult,
)
from uniassist.ai.parsing import (
    extract_message_content,
    parse_json_content,
    parse_structured_answer,
    parse_verification_payload,
)
from uniassist.ai.prompting import (
    build_generation_messages,
    build_verification_messages,
)
from uniassist.ai.providers.nvidia_client import NVIDIAClient, NVIDIAClientConfig


class NVIDIAProvider:
    """Grounded answer generation and verification via NVIDIA NIM."""

    def __init__(self, client: NVIDIAClient | None = None) -> None:
        self._client = client or NVIDIAClient(NVIDIAClientConfig.from_env())

    @property
    def model_name(self) -> str:
        return self._client.model

    def generate_answer(
        self,
        question: Question,
        evidence: list[EvidenceItem],
    ) -> CandidateAnswer:
        messages = build_generation_messages(question, evidence)
        response = self._client.chat_completion(messages)
        content = extract_message_content(response)
        payload = parse_json_content(content)
        structured = parse_structured_answer(payload)
        if structured.insufficient_evidence and not structured.answer:
            structured = StructuredAnswerPayload(
                answer=(
                    "The available documents do not contain sufficient evidence "
                    "to answer this question reliably."
                ),
                claims=(),
                insufficient_evidence=True,
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
        messages = build_verification_messages(question, candidate, evidence)
        response = self._client.chat_completion(messages)
        content = extract_message_content(response)
        payload = parse_verification_payload(parse_json_content(content))
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

