"""Embedding provider abstraction and local implementations."""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

DEFAULT_DIMENSION = 128


class EmbeddingProvider(Protocol):
    """Generate vector embeddings for retrieval."""

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension."""

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple text strings."""


class DeterministicEmbeddingProvider:
    """Hash-based local embeddings for development and tests.

    Same input text always produces the same unit-normalized vector.
    No external models or network access required.
    """

    provider_name = "deterministic"

    def __init__(self, dimension: int = DEFAULT_DIMENSION) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def info(self):
        from uniassist.rag.nvidia_embeddings import EmbeddingProviderInfo

        return EmbeddingProviderInfo(
            provider_name=self.provider_name,
            model_name="deterministic-hash-v1",
            dimension=self._dimension,
        )

    def embed_text(self, text: str) -> list[float]:
        return _text_to_vector(text, self._dimension)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


def _text_to_vector(text: str, dimension: int) -> list[float]:
    vector = [0.0] * dimension
    normalized = text.lower().strip()
    if not normalized:
        return vector

    features = normalized.split()
    features.extend(_bigrams(features))
    features.extend(_character_trigrams(normalized))

    for feature in features:
        digest = hashlib.sha256(feature.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0.0:
        return vector
    return [value / magnitude for value in vector]


def _bigrams(tokens: list[str]) -> list[str]:
    return [f"{left} {right}" for left, right in zip(tokens, tokens[1:], strict=False)]


def _character_trigrams(text: str) -> list[str]:
    compact = "".join(ch for ch in text if ch.isalnum() or ch.isspace())
    if len(compact) < 3:
        return [compact] if compact else []
    return [compact[index : index + 3] for index in range(len(compact) - 2)]
