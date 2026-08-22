"""Evidence conversion helpers."""

from __future__ import annotations

from uniassist.ai.models import EvidenceItem
from uniassist.documents.models import DocumentRecord
from uniassist.rag.models import RetrievedChunk


def evidence_from_retrieved(
    chunks: list[RetrievedChunk],
    *,
    records: dict[str, DocumentRecord] | None = None,
) -> list[EvidenceItem]:
    """Convert retrieved chunks into structured evidence items."""
    records = records or {}
    return [
        EvidenceItem(
            chunk_id=item.chunk.chunk_id,
            document_id=item.chunk.document_id,
            title=item.chunk.title,
            text=item.chunk.text,
            page_number=item.chunk.page_number,
            section=item.chunk.section,
            source=item.chunk.source,
            source_url=item.chunk.source_url,
            document_version=item.chunk.document_version,
            source_sha256=item.chunk.source_sha256,
            effective_date=_effective_date(records.get(item.chunk.document_id)),
            similarity_score=item.similarity_score,
        )
        for item in chunks
    ]


def _effective_date(record: DocumentRecord | None) -> str | None:
    if record is None or record.effective_date is None:
        return None
    return record.effective_date.isoformat()
