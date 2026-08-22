"""Evidence retrieval over indexed chunks."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from uniassist.documents.models import DocumentRecord
from uniassist.rag.embedding_factory import (
    create_embedding_provider,
    default_min_score_for,
)
from uniassist.rag.embeddings import EmbeddingProvider
from uniassist.rag.indexing import IndexingService
from uniassist.rag.models import RetrievedChunk
from uniassist.rag.vector_store import VectorStore


class RetrievalError(ValueError):
    """Raised when a retrieval request is invalid."""


@dataclass(frozen=True)
class RetrievalConfig:
    """Configuration for evidence retrieval."""

    top_k: int = 5
    min_score: float | None = None
    max_chunks_per_document: int = 2


@dataclass(frozen=True)
class RetrievalResult:
    """Retrieval output with safe timing metadata."""

    chunks: list[RetrievedChunk]
    retrieval_latency_ms: float
    top_score: float | None
    potentially_conflicting: bool = False


class Retriever:
    """Retrieve ranked evidence chunks for a user query."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider | None = None,
        indexing_service: IndexingService | None = None,
        *,
        require_eligibility: bool = True,
        config: RetrievalConfig | None = None,
    ) -> None:
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider or create_embedding_provider()
        self._indexing_service = indexing_service
        self._require_eligibility = require_eligibility
        self._config = config or RetrievalConfig()

    @classmethod
    def default(
        cls,
        project_root: Path | None = None,
        *,
        require_eligibility: bool = True,
        config: RetrievalConfig | None = None,
    ) -> Retriever:
        indexing = IndexingService.default(
            project_root=project_root,
            require_eligibility=require_eligibility,
        )
        return cls(
            vector_store=indexing.vector_store,
            embedding_provider=indexing.embedding_provider,
            indexing_service=indexing,
            require_eligibility=require_eligibility,
            config=config,
        )

    def retrieve(self, query: str, *, top_k: int | None = None) -> list[RetrievedChunk]:
        """Return ranked evidence chunks for *query*."""
        return self.retrieve_with_metadata(query, top_k=top_k).chunks

    def retrieve_with_metadata(
        self,
        query: str,
        *,
        top_k: int | None = None,
    ) -> RetrievalResult:
        cleaned = query.strip()
        if not cleaned:
            raise RetrievalError("query must not be empty")
        limit = self._config.top_k if top_k is None else top_k
        if limit <= 0:
            raise RetrievalError("top_k must be positive")

        min_score = self._config.min_score
        if min_score is None:
            min_score = default_min_score_for(self._embedding_provider)

        allowed_document_ids = None
        document_records: dict[str, DocumentRecord] = {}
        if self._indexing_service is not None:
            document_store = self._indexing_service.document_store
            document_records = {
                record.document_id: record
                for record in document_store.list_records()
            }
            if self._require_eligibility:
                allowed_document_ids = self._indexing_service.eligible_document_ids()

        started = time.perf_counter()
        query_vector = self._embedding_provider.embed_text(cleaned)
        results = self._vector_store.search(
            query_vector,
            top_k=limit,
            allowed_document_ids=allowed_document_ids,
            min_score=min_score,
            max_chunks_per_document=self._config.max_chunks_per_document,
        )
        results = self._apply_version_preference(results, document_records)
        conflicting = self._detect_potential_conflicts(results, document_records)
        latency_ms = (time.perf_counter() - started) * 1000
        top_score = results[0].similarity_score if results else None
        return RetrievalResult(
            chunks=results,
            retrieval_latency_ms=latency_ms,
            top_score=top_score,
            potentially_conflicting=conflicting,
        )

    def _apply_version_preference(
        self,
        results: list[RetrievedChunk],
        records: dict[str, DocumentRecord],
    ) -> list[RetrievedChunk]:
        if not results or not records:
            return results

        def authority_key(item: RetrievedChunk) -> tuple:
            record = records.get(item.chunk.document_id)
            effective = record.effective_date if record else None
            version = record.version if record else ""
            uploaded = record.uploaded_at if record else None
            return (
                effective or date.min,
                version or "",
                uploaded or item.chunk.chunk_id,
            )

        by_document: dict[str, list[RetrievedChunk]] = {}
        for item in results:
            by_document.setdefault(item.chunk.document_id, []).append(item)

        preferred_documents = {
            document_id: max(items, key=authority_key).chunk.document_id
            for document_id, items in by_document.items()
        }
        del preferred_documents  # reserved for future supersession rules

        return sorted(
            results,
            key=lambda item: (
                authority_key(item)[0].toordinal()
                if authority_key(item)[0] != date.min
                else 0,
                item.similarity_score,
            ),
            reverse=True,
        )

    def _detect_potential_conflicts(
        self,
        results: list[RetrievedChunk],
        records: dict[str, DocumentRecord],
    ) -> bool:
        durations: set[str] = set()
        for item in results:
            record = records.get(item.chunk.document_id)
            if record is None:
                continue
            hint = _duration_hint(item.chunk.text)
            if hint is not None:
                durations.add(hint)
        return len(durations) > 1


def _duration_hint(text: str) -> str | None:
    import re

    match = re.search(r"\b(\d+)\s*(month|months|year|years)\b", text.lower())
    return match.group(0) if match else None
