"""Tests for embedding providers."""

from __future__ import annotations

import pytest

from uniassist.rag.embeddings import DeterministicEmbeddingProvider


def test_same_text_produces_same_vector() -> None:
    provider = DeterministicEmbeddingProvider(dimension=64)
    first = provider.embed_text("academic leave request")
    second = provider.embed_text("academic leave request")
    assert first == second


def test_vector_dimension() -> None:
    provider = DeterministicEmbeddingProvider(dimension=32)
    vector = provider.embed_text("hello")
    assert len(vector) == 32


def test_batch_embedding_matches_single() -> None:
    provider = DeterministicEmbeddingProvider()
    texts = ["library hours", "academic leave"]
    batch = provider.embed_batch(texts)
    assert batch[0] == provider.embed_text(texts[0])
    assert batch[1] == provider.embed_text(texts[1])


def test_dimension_must_be_positive() -> None:
    with pytest.raises(ValueError, match="dimension"):
        DeterministicEmbeddingProvider(dimension=0)
