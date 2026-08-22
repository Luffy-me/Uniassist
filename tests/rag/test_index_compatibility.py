"""Tests for vector index embedding compatibility."""

from __future__ import annotations

import pytest

from tests.rag.conftest import ingest_and_process_text
from uniassist.rag.embeddings import DeterministicEmbeddingProvider
from uniassist.rag.index_metadata import (
    IndexCompatibilityError,
    IndexManifest,
    IndexManifestStore,
)
from uniassist.rag.indexing import IndexingService
from uniassist.rag.vector_store import VectorStore


def test_incompatible_embedding_provider_requires_rebuild(rag_stack, tmp_path) -> None:
    record = ingest_and_process_text(
        rag_stack,
        filename="leave.txt",
        content="Students may request academic leave.",
        title="Academic Leave Regulations",
        source="SUSU",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_store = IndexManifestStore(manifest_path)
    manifest_store.save(
        IndexManifest(
            provider_name="other",
            embedding_model="other-model",
            dimension=128,
        )
    )
    service = IndexingService(
        document_store=rag_stack["document_store"],
        processing_store=rag_stack["processing_store"],
        vector_store=VectorStore(),
        embedding_provider=DeterministicEmbeddingProvider(dimension=128),
        require_eligibility=True,
        metadata_path=tmp_path / "documents.json",
        manifest_path=manifest_path,
    )
    with pytest.raises(IndexCompatibilityError, match="incompatible"):
        service.index_document(record.document_id)
