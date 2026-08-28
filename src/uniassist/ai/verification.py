"""Claim-level answer verification."""

from __future__ import annotations

import re
import time
from datetime import date

from uniassist.ai.claim_verification import (
    ClaimAssessment,
    ClaimSupportStatus,
    DeterministicSemanticVerifier,
    SemanticVerifier,
)
from uniassist.ai.models import (
    AnswerClaim,
    CandidateAnswer,
    Citation,
    EvidenceItem,
    Question,
    RefusalReason,
    VerificationResult,
)
from uniassist.documents.models import DocumentRecord, DocumentStatus, VerificationState
from uniassist.documents.store import DocumentStore


class VerificationEngine:
    """Verify candidate answers against retrieved evidence and corpus metadata."""

    def __init__(
        self,
        document_store: DocumentStore,
        *,
        semantic_verifier: SemanticVerifier | None = None,
    ) -> None:
        self._document_store = document_store
        self._semantic_verifier = semantic_verifier or DeterministicSemanticVerifier()

    def verify(
        self,
        question: Question,
        candidate: CandidateAnswer,
        evidence: list[EvidenceItem],
    ) -> VerificationResult:
        started = time.perf_counter()
        evidence_by_id = {item.chunk_id: item for item in evidence}
        eligible_records = {
            record.document_id: record
            for record in self._document_store.list_records()
            if self._is_eligible(record)
        }

        structural_errors = self._structural_validation(candidate, evidence_by_id)
        supported: list[str] = []
        unsupported: list[str] = []
        citation_errors: list[str] = []
        assessments: list[str] = []

        if structural_errors:
            return self._result(
                verified=False,
                supported=supported,
                unsupported=unsupported,
                citation_errors=structural_errors,
                contradictions=(),
                assessments=assessments,
                refusal=RefusalReason.INVALID_CITATION,
                started=started,
            )

        for claim in candidate.claims:
            layer = self._validate_claim_layers(
                question,
                claim,
                evidence_by_id=evidence_by_id,
                eligible_records=eligible_records,
            )
            assessments.append(f"{claim.text} -> {layer.status.value}: {layer.reason}")
            if layer.status == ClaimSupportStatus.SUPPORTED:
                supported.append(claim.text)
            elif layer.status == ClaimSupportStatus.CONTRADICTED:
                unsupported.append(claim.text)
            else:
                unsupported.append(claim.text)

        citation_errors.extend(
            self._citation_validation(candidate, evidence_by_id, eligible_records)
        )
        contradictions = self._detect_contradictions(evidence, eligible_records)

        verified = (
            bool(candidate.answer_text)
            and bool(candidate.claims)
            and not unsupported
            and not citation_errors
            and not contradictions
        )
        confidence = 1.0 if verified else 0.0
        if supported and (unsupported or citation_errors or contradictions):
            confidence = len(supported) / max(
                len(supported) + len(unsupported) + len(citation_errors),
                1,
            )

        refusal = None
        if not verified:
            if contradictions:
                refusal = RefusalReason.CONTRADICTORY_EVIDENCE
            elif citation_errors:
                refusal = RefusalReason.INVALID_CITATION
            elif unsupported:
                refusal = RefusalReason.UNSUPPORTED_CLAIM
            elif not evidence:
                refusal = RefusalReason.NO_RELEVANT_EVIDENCE
            else:
                refusal = RefusalReason.INSUFFICIENT_EVIDENCE

        return self._result(
            verified=verified,
            supported=supported,
            unsupported=unsupported,
            citation_errors=citation_errors,
            contradictions=contradictions,
            assessments=assessments,
            refusal=refusal,
            started=started,
            confidence=confidence,
        )

    def repair_candidate(
        self,
        candidate: CandidateAnswer,
        verification: VerificationResult,
    ) -> CandidateAnswer | None:
        """Remove unsupported claims when enough supported claims remain."""
        if verification.verified:
            return candidate
        if not verification.supported_claims or not verification.unsupported_claims:
            return None
        if len(verification.supported_claims) < len(verification.unsupported_claims):
            return None
        supported_set = set(verification.supported_claims)
        repaired_claims = tuple(
            claim for claim in candidate.claims if claim.text in supported_set
        )
        if not repaired_claims:
            return None
        repaired_answer = " ".join(claim.text for claim in repaired_claims)
        return CandidateAnswer(
            answer_text=repaired_answer,
            claims=repaired_claims,
            evidence=candidate.evidence,
            model=candidate.model,
            generated_at=candidate.generated_at,
        )

    def build_citations(
        self,
        candidate: CandidateAnswer,
        evidence: list[EvidenceItem],
    ) -> tuple[Citation, ...]:
        evidence_by_id = {item.chunk_id: item for item in evidence}
        citations: list[Citation] = []
        seen: set[str] = set()
        for claim in candidate.claims:
            for chunk_id in claim.evidence_ids:
                if chunk_id in seen or chunk_id not in evidence_by_id:
                    continue
                item = evidence_by_id[chunk_id]
                citations.append(
                    Citation(
                        chunk_id=item.chunk_id,
                        document_id=item.document_id,
                        title=item.title,
                        page_number=item.page_number,
                        section=item.section,
                        source=item.source,
                        source_url=item.source_url,
                    )
                )
                seen.add(chunk_id)
        return tuple(citations)

    def _validate_claim_layers(
        self,
        question: Question,
        claim: AnswerClaim,
        *,
        evidence_by_id: dict[str, EvidenceItem],
        eligible_records: dict[str, DocumentRecord],
    ) -> ClaimAssessment:
        if not claim.text.strip():
            return ClaimAssessment(
                claim_text=claim.text,
                status=ClaimSupportStatus.UNSUPPORTED,
                reason="empty claim",
            )
        if not claim.evidence_ids:
            return ClaimAssessment(
                claim_text=claim.text,
                status=ClaimSupportStatus.UNSUPPORTED,
                reason="claim has no evidence_ids",
            )
        cited_items: list[EvidenceItem] = []
        for chunk_id in claim.evidence_ids:
            if chunk_id not in evidence_by_id:
                return ClaimAssessment(
                    claim_text=claim.text,
                    status=ClaimSupportStatus.UNSUPPORTED,
                    reason="unknown evidence_id",
                )
            item = evidence_by_id[chunk_id]
            if item.document_id not in eligible_records:
                return ClaimAssessment(
                    claim_text=claim.text,
                    status=ClaimSupportStatus.UNSUPPORTED,
                    reason="evidence from ineligible document",
                )
            cited_items.append(item)
        return self._semantic_verifier.verify_claim(question, claim, cited_items)

    def _structural_validation(
        self,
        candidate: CandidateAnswer,
        evidence_by_id: dict[str, EvidenceItem],
    ) -> list[str]:
        errors: list[str] = []
        if not candidate.answer_text.strip():
            errors.append("answer text is empty")
        if not candidate.claims:
            errors.append("no claims provided")
        for claim in candidate.claims:
            if not claim.text.strip():
                errors.append("empty claim text")
            seen_ids: set[str] = set()
            for chunk_id in claim.evidence_ids:
                if chunk_id in seen_ids:
                    errors.append(f"duplicate citation id: {chunk_id}")
                seen_ids.add(chunk_id)
                if chunk_id not in evidence_by_id:
                    errors.append(f"unknown evidence id: {chunk_id}")
        return errors

    def _citation_validation(
        self,
        candidate: CandidateAnswer,
        evidence_by_id: dict[str, EvidenceItem],
        eligible_records: dict[str, DocumentRecord],
    ) -> list[str]:
        errors: list[str] = []
        for claim in candidate.claims:
            for chunk_id in claim.evidence_ids:
                if chunk_id not in evidence_by_id:
                    errors.append(claim.text)
                    continue
                item = evidence_by_id[chunk_id]
                if item.document_id not in eligible_records:
                    errors.append(claim.text)
        return errors

    def _detect_contradictions(
        self,
        evidence: list[EvidenceItem],
        eligible_records: dict[str, DocumentRecord],
    ) -> list[str]:
        by_topic: dict[str, list[tuple[EvidenceItem, DocumentRecord]]] = {}
        for item in evidence:
            record = eligible_records.get(item.document_id)
            if record is None:
                continue
            topic = self._topic_key(item.text)
            by_topic.setdefault(topic, []).append((item, record))

        conflicts: list[str] = []
        for topic, entries in by_topic.items():
            if len(entries) < 2:
                continue
            durations = {
                self._duration_hint(entry[0].text)
                for entry in entries
                if self._duration_hint(entry[0].text) is not None
            }
            if len(durations) > 1:
                active_versions = {entry[1].document_id for entry in entries}
                if len(active_versions) > 1:
                    preferred = self._preferred_record(entries)
                    conflicts.append(
                        f"Conflicting duration statements for topic '{topic}' "
                        f"across active documents (preferred: {preferred.title})."
                    )
        return conflicts

    def _topic_key(self, text: str) -> str:
        keywords = sorted(_keywords(text))
        return " ".join(keywords[:4]) if keywords else text[:40].lower()

    def _duration_hint(self, text: str) -> str | None:
        match = re.search(r"\b(\d+)\s*(month|months|year|years)\b", text.lower())
        return match.group(0) if match else None

    def _preferred_record(
        self,
        entries: list[tuple[EvidenceItem, DocumentRecord]],
    ) -> DocumentRecord:
        def sort_key(entry: tuple[EvidenceItem, DocumentRecord]) -> tuple:
            _, record = entry
            effective = record.effective_date or date.min
            version = record.version or ""
            return (effective, version, record.uploaded_at)

        return max(entries, key=sort_key)[1]

    def _is_eligible(self, record: DocumentRecord) -> bool:
        return (
            record.status == DocumentStatus.ACTIVE
            and record.verification_state == VerificationState.VERIFIED
        )

    def _result(
        self,
        *,
        verified: bool,
        supported: list[str],
        unsupported: list[str],
        citation_errors: list[str],
        contradictions: list[str],
        assessments: list[str],
        refusal: RefusalReason | None,
        started: float,
        confidence: float = 0.0,
    ) -> VerificationResult:
        del started
        return VerificationResult(
            verified=verified,
            confidence=confidence if not verified else 1.0,
            supported_claims=tuple(supported),
            unsupported_claims=tuple(unsupported),
            contradictions=tuple(contradictions),
            citation_errors=tuple(citation_errors),
            reasoning_summary=self._summary(
                verified=verified,
                supported=supported,
                unsupported=unsupported,
                contradictions=contradictions,
                citation_errors=citation_errors,
            ),
            refusal_reason=refusal,
            claim_assessments=tuple(assessments),
        )

    def _summary(
        self,
        *,
        verified: bool,
        supported: list[str],
        unsupported: list[str],
        contradictions: list[str],
        citation_errors: list[str],
    ) -> str:
        if verified:
            return (
                f"All {len(supported)} claim(s) are supported by eligible evidence."
            )
        parts = []
        if unsupported:
            parts.append(f"{len(unsupported)} unsupported claim(s)")
        if citation_errors:
            parts.append(f"{len(citation_errors)} citation error(s)")
        if contradictions:
            parts.append(f"{len(contradictions)} contradiction(s)")
        return "; ".join(parts) or "verification failed"


def _keywords(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    stopwords = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "is",
        "are",
        "may",
        "be",
        "by",
        "with",
        "as",
        "at",
        "it",
        "this",
        "that",
        "their",
        "students",
        "student",
        "university",
    }
    return {token for token in tokens if token not in stopwords and len(token) > 2}
