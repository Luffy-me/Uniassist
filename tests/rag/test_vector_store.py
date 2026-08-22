"""Tests for vector store and cosine similarity."""

from __future__ import annotations

import pytest

from uniassist.rag.models import Chunk
from uniassist.rag.vector_store import (
    VectorDimensionError,
    VectorStore,
    cosine_similarity,
)


def _chunk(chunk_id: str, document_id: str, text: str, index: int = 0) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=document_id,
        text=text,
        chunk_index=index,
        page_number=1,
        section="s1",
        source_sha256="sha",
        document_version="v1",
        source="Registrar",
        source_url=None,
        title="Rules",
    )


def test_add_and_get() -> None:
    store = VectorStore()
    chunk = _chunk("c1", "d1", "hello")
    store.add(chunk, [1.0, 0.0])
    assert store.get("c1") == chunk


def test_search_returns_top_k_sorted() -> None:
    store = VectorStore()
    store.add(_chunk("c1", "d1", "library hours"), [1.0, 0.0])
    store.add(_chunk("c2", "d1", "academic leave"), [0.0, 1.0])
    results = store.search([0.0, 1.0], top_k=2)
    assert len(results) == 2
    assert results[0].chunk.chunk_id == "c2"
    assert results[0].rank == 1
    assert results[0].similarity_score >= results[1].similarity_score


def test_empty_store_returns_no_results() -> None:
    store = VectorStore()
    assert store.search([1.0, 0.0], top_k=3) == []


def test_zero_vectors_return_zero_similarity() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_dimension_mismatch_raises() -> None:
    with pytest.raises(VectorDimensionError):
        cosine_similarity([1.0], [1.0, 0.0])


def test_duplicate_chunk_id_with_different_metadata_raises() -> None:
    store = VectorStore()
    store.add(_chunk("c1", "d1", "hello"), [1.0, 0.0])
    different = _chunk("c1", "d2", "hello")
    with pytest.raises(ValueError, match="duplicate chunk_id"):
        store.add(different, [1.0, 0.0])


def test_delete_document_removes_chunks() -> None:
    store = VectorStore()
    store.add(_chunk("c1", "d1", "one"), [1.0, 0.0])
    store.add(_chunk("c2", "d1", "two"), [0.0, 1.0])
    store.add(_chunk("c3", "d2", "three"), [1.0, 1.0])
    removed = store.delete_document("d1")
    assert removed == 2
    assert store.get("c3") is not None
