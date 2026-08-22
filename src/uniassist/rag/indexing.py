"""Indexing processed documents into the vector store."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from uniassist.documents.models import DocumentRecord, DocumentStatus, VerificationState
from uniassist.documents.store import DocumentStore
from uniassist.processing.models import ProcessingStatus
from uniassist.processing.store import ProcessingStore
from uniassist.rag.chunking import chunk_document
from uniassist.rag.embedding_factory import create_embedding_provider
from uniassist.rag.embeddings import EmbeddingProvider
from uniassist.rag.index_metadata import (
    IndexCompatibilityError,
    IndexManifest,
    IndexManifestStore,
)
from uniassist.rag.models import Chunk, ChunkConfig
from uniassist.rag.nvidia_embeddings import EmbeddingProviderInfo
from uniassist.rag.vector_store import JsonVectorStore, VectorStore


class IndexingEligibilityError(ValueError):
    """Raised when a document is not eligible for indexing."""


@dataclass(frozen=True)
class IndexResult:
    """Outcome of indexing one document."""

    document_id: str
    chunks_indexed: int
    indexed_at: datetime


@dataclass(frozen=True)
class IndexStats:
    """Summary statistics for the RAG index."""

    total_chunks: int
    indexed_documents: int
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    provider_name: str | None = None


@dataclass(frozen=True)
class RebuildReport:
    """Summary of a full index rebuild."""

    documents_indexed: int
    chunks_created: int
    embeddings_generated: int
    embedding_model: str
    embedding_dimension: int
    provider_name: str
    duration_seconds: float


class IndexingService:
    """Build and maintain the searchable evidence index."""

    def __init__(
        self,
        document_store: DocumentStore,
        processing_store: ProcessingStore,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider | None = None,
        chunk_config: ChunkConfig | None = None,
        *,
        require_eligibility: bool = True,
        metadata_path: Path | None = None,
        manifest_path: Path | None = None,
        manifest_store: IndexManifestStore | None = None,
    ) -> None:
        self._document_store = document_store
        self._processing_store = processing_store
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider or create_embedding_provider()
        self._chunk_config = chunk_config or ChunkConfig()
        self._require_eligibility = require_eligibility
        self._metadata_path = metadata_path
        if manifest_store is not None:
            self._manifest_store = manifest_store
        elif manifest_path is not None:
            self._manifest_store = IndexManifestStore(manifest_path)
        else:
            self._manifest_store = None

    @property
    def vector_store(self) -> VectorStore:
        return self._vector_store

    @property
    def embedding_provider(self) -> EmbeddingProvider:
        return self._embedding_provider

    @property
    def document_store(self) -> DocumentStore:
        return self._document_store

    @classmethod
    def default(
        cls,
        project_root: Path | None = None,
        *,
        require_eligibility: bool = True,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> IndexingService:
        from uniassist.persistence.factory import build_persistence

        root = project_root or Path.cwd()
        persistence = build_persistence(root)
        return cls(
            document_store=persistence.document_store,
            processing_store=persistence.processing_store,
            vector_store=persistence.vector_store,
            embedding_provider=embedding_provider,
            metadata_path=persistence.rag_metadata_path,
            manifest_store=persistence.manifest_store,
            require_eligibility=require_eligibility,
        )

    def index_document(self, document_id: str, *, rebuild: bool = False) -> IndexResult:
        """Index one document after eligibility and processing checks."""
        self._ensure_compatible_index(rebuild=rebuild)
        record = self._document_store.get(document_id)
        if record is None:
            raise KeyError(f"document not found: {document_id}")

        if self._require_eligibility:
            self._ensure_eligible(record)

        processing = self._processing_store.get_result(document_id)
        if processing is None or processing.status != ProcessingStatus.COMPLETED:
            raise ValueError(
                f"document {document_id} has no completed processing result"
            )

        normalized = self._processing_store.load_normalized(
            document_id,
            record.sha256,
        )
        chunks = chunk_document(normalized, self._chunk_config)
        chunks = [
            Chunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                text=chunk.text,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                section=chunk.section,
                source_sha256=chunk.source_sha256,
                document_version=record.version,
                source=chunk.source,
                source_url=chunk.source_url,
                title=chunk.title,
            )
            for chunk in chunks
        ]
        if not chunks:
            raise ValueError(f"document {document_id} produced no chunks")

        self._vector_store.delete_document(document_id)
        vectors = self._embedding_provider.embed_batch([chunk.text for chunk in chunks])
        for chunk, vector in zip(chunks, vectors, strict=True):
            self._vector_store.add(chunk, vector)

        self._record_indexed_document(record)
        self._save_manifest()
        self._persist_vector_store()
        return IndexResult(
            document_id=document_id,
            chunks_indexed=len(chunks),
            indexed_at=datetime.now(UTC),
        )

    def index_all_eligible(self, *, rebuild: bool = False) -> list[IndexResult]:
        """Index every eligible, processed document."""
        results: list[IndexResult] = []
        for record in self._document_store.list_records():
            if not self._is_eligible(record):
                continue
            processing = self._processing_store.get_result(record.document_id)
            if processing is None or processing.status != ProcessingStatus.COMPLETED:
                continue
            results.append(self.index_document(record.document_id, rebuild=rebuild))
        return results

    def rebuild_index(self) -> RebuildReport:
        """Explicitly rebuild the entire vector index from scratch."""
        started = time.perf_counter()
        self._vector_store.clear()
        if self._manifest_store is not None:
            self._manifest_store.clear()
        if isinstance(self._vector_store, JsonVectorStore):
            if self._vector_store.index_path.exists():
                self._vector_store.index_path.unlink()

        results = self.index_all_eligible(rebuild=True)
        chunks = len(self._vector_store)
        info = self._provider_info()
        duration = time.perf_counter() - started
        return RebuildReport(
            documents_indexed=len(results),
            chunks_created=chunks,
            embeddings_generated=chunks,
            embedding_model=info.model_name,
            embedding_dimension=info.dimension,
            provider_name=info.provider_name,
            duration_seconds=duration,
        )

    def stats(self) -> IndexStats:
        chunks = self._vector_store.list_chunks()
        document_ids = {chunk.document_id for chunk in chunks}
        manifest = self._manifest_store.load() if self._manifest_store else None
        return IndexStats(
            total_chunks=len(chunks),
            indexed_documents=len(document_ids),
            embedding_model=manifest.embedding_model if manifest else None,
            embedding_dimension=manifest.dimension if manifest else None,
            provider_name=manifest.provider_name if manifest else None,
        )

    def eligible_document_ids(self) -> set[str]:
        if not self._require_eligibility:
            return {chunk.document_id for chunk in self._vector_store.list_chunks()}
        return {
            record.document_id
            for record in self._document_store.list_records()
            if self._is_eligible(record)
        }

    def _provider_info(self) -> EmbeddingProviderInfo:
        info = getattr(self._embedding_provider, "info", None)
        if info is not None:
            return info
        return EmbeddingProviderInfo(
            provider_name=getattr(self._embedding_provider, "provider_name", "unknown"),
            model_name="unknown",
            dimension=self._embedding_provider.dimension,
        )

    def _ensure_compatible_index(self, *, rebuild: bool) -> None:
        if self._manifest_store is None:
            return
        manifest = self._manifest_store.load()
        info = self._provider_info()
        dimension = self._embedding_provider.dimension
        if manifest is None:
            if len(self._vector_store) == 0 or rebuild:
                return
            raise IndexCompatibilityError(
                "vector index exists without manifest metadata; "
                "run `python -m uniassist.rag.cli rebuild` explicitly"
            )
        if rebuild:
            return
        if not manifest.is_compatible_with(
            provider_name=info.provider_name,
            embedding_model=info.model_name,
            dimension=dimension,
        ):
            raise IndexCompatibilityError(
                "embedding provider/model/dimension incompatible with existing index; "
                "run `python -m uniassist.rag.cli rebuild` explicitly"
            )

    def _save_manifest(self) -> None:
        if self._manifest_store is None:
            return
        info = self._provider_info()
        manifest = IndexManifest(
            provider_name=info.provider_name,
            embedding_model=info.model_name,
            dimension=self._embedding_provider.dimension,
        )
        self._manifest_store.save(manifest)

    def _is_eligible(self, record: DocumentRecord) -> bool:
        return (
            record.status == DocumentStatus.ACTIVE
            and record.verification_state == VerificationState.VERIFIED
        )

    def _ensure_eligible(self, record: DocumentRecord) -> None:
        if not self._is_eligible(record):
            raise IndexingEligibilityError(
                "only ACTIVE + VERIFIED documents can be indexed; "
                f"document {record.document_id} is "
                f"{record.status.value}/{record.verification_state.value}"
            )

    def _record_indexed_document(self, record: DocumentRecord) -> None:
        if self._metadata_path is None:
            return
        entries = self._load_index_metadata()
        entries[record.document_id] = {
            "document_id": record.document_id,
            "source_sha256": record.sha256,
            "document_version": record.version,
            "indexed_at": datetime.now(UTC).isoformat(),
        }
        self._write_index_metadata(entries)

    def _load_index_metadata(self) -> dict[str, dict]:
        if self._metadata_path is None or not self._metadata_path.exists():
            return {}
        return json.loads(self._metadata_path.read_text(encoding="utf-8"))

    def _write_index_metadata(self, entries: dict[str, dict]) -> None:
        if self._metadata_path is None:
            return
        self._metadata_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._metadata_path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, self._metadata_path)

    def _persist_vector_store(self) -> None:
        if isinstance(self._vector_store, JsonVectorStore):
            self._vector_store.save()
