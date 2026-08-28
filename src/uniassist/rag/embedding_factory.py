"""Embedding provider selection."""

from __future__ import annotations

from uniassist.rag.embeddings import DeterministicEmbeddingProvider, EmbeddingProvider


def create_embedding_provider(
    *,
    force_deterministic: bool = False,
) -> EmbeddingProvider:
    """Return the local hash embedding provider.

    Chat uses Groq. Retrieval embeddings stay local so the API can start
    without a third-party embedding service.
    """
    del force_deterministic
    return DeterministicEmbeddingProvider()


def default_min_score_for(provider: EmbeddingProvider) -> float:
    """Return a similarity threshold for the active embedding provider."""
    del provider
    return 0.0
