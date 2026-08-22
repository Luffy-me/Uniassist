"""Local vector store with cosine similarity search."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

from uniassist.rag.models import Chunk, RetrievedChunk


@dataclass(frozen=True)
class SearchConfig:
    """Configuration for vector similarity search."""

    top_k: int = 5
    min_score: float = 0.0
    max_chunks_per_document: int = 2


class VectorDimensionError(ValueError):
    """Raised when embedding dimensions do not match."""


class VectorStore:
    """Store chunk embeddings and search by cosine similarity."""

    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}
        self._vectors: dict[str, list[float]] = {}

    def add(self, chunk: Chunk, vector: list[float]) -> None:
        """Add or replace a chunk embedding."""
        if chunk.chunk_id in self._chunks and self._chunks[chunk.chunk_id] != chunk:
            raise ValueError(
                f"duplicate chunk_id with different metadata: {chunk.chunk_id}"
            )
        if self._vectors:
            existing_dim = next(iter(self._vectors.values()))
            if len(vector) != len(existing_dim):
                raise VectorDimensionError(
                    f"expected dimension {len(existing_dim)}, got {len(vector)}"
                )
        self._chunks[chunk.chunk_id] = chunk
        self._vectors[chunk.chunk_id] = list(vector)

    def delete(self, chunk_id: str) -> None:
        """Remove a chunk from the index."""
        self._chunks.pop(chunk_id, None)
        self._vectors.pop(chunk_id, None)

    def delete_document(self, document_id: str) -> int:
        """Remove all chunks belonging to a document."""
        to_remove = [
            chunk_id
            for chunk_id, chunk in self._chunks.items()
            if chunk.document_id == document_id
        ]
        for chunk_id in to_remove:
            self.delete(chunk_id)
        return len(to_remove)

    def get(self, chunk_id: str) -> Chunk | None:
        """Return a chunk by ID."""
        return self._chunks.get(chunk_id)

    def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int,
        allowed_document_ids: set[str] | None = None,
        min_score: float = 0.0,
        max_chunks_per_document: int | None = None,
    ) -> list[RetrievedChunk]:
        """Return top-k chunks ranked by cosine similarity."""
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if not self._vectors:
            return []

        scored: list[tuple[float, Chunk]] = []
        for chunk_id, vector in self._vectors.items():
            chunk = self._chunks[chunk_id]
            if (
                allowed_document_ids is not None
                and chunk.document_id not in allowed_document_ids
            ):
                continue
            score = cosine_similarity(query_embedding, vector)
            if score < min_score:
                continue
            scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected: list[tuple[float, Chunk]] = []
        per_document: dict[str, int] = {}
        for score, chunk in scored:
            if len(selected) >= top_k:
                break
            if max_chunks_per_document is not None:
                count = per_document.get(chunk.document_id, 0)
                if count >= max_chunks_per_document:
                    continue
                per_document[chunk.document_id] = count + 1
            selected.append((score, chunk))

        return [
            RetrievedChunk(chunk=chunk, similarity_score=score, rank=index + 1)
            for index, (score, chunk) in enumerate(selected)
        ]

    def __len__(self) -> int:
        return len(self._chunks)

    def list_chunks(self) -> list[Chunk]:
        return list(self._chunks.values())

    def clear(self) -> None:
        """Remove all chunks and vectors."""
        self._chunks.clear()
        self._vectors.clear()

    def to_dict(self) -> dict:
        return {
            "chunks": [chunk.to_dict() for chunk in self._chunks.values()],
            "vectors": self._vectors,
        }

    @classmethod
    def from_dict(cls, data: dict) -> VectorStore:
        store = cls()
        chunks = {item["chunk_id"]: Chunk.from_dict(item) for item in data["chunks"]}
        vectors = data["vectors"]
        for chunk_id, vector in vectors.items():
            store.add(chunks[chunk_id], vector)
        return store


class JsonVectorStore(VectorStore):
    """Persisted vector store backed by a JSON file."""

    def __init__(self, index_path: Path) -> None:
        super().__init__()
        self.index_path = index_path
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        if self.index_path.exists():
            self._load()

    def save(self) -> None:
        payload = self.to_dict()
        temp_path = self.index_path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, self.index_path)

    def _load(self) -> None:
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        loaded = VectorStore.from_dict(data)
        self._chunks = loaded._chunks
        self._vectors = loaded._vectors


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(left) != len(right):
        raise VectorDimensionError(
            f"dimension mismatch: {len(left)} vs {len(right)}"
        )
    if not left or not right:
        return 0.0

    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)
