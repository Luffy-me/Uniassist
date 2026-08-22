"""RAG data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkConfig:
    """Configuration for deterministic text chunking."""

    max_chars: int = 800
    overlap: int = 100

    def __post_init__(self) -> None:
        if self.max_chars <= 0:
            raise ValueError("max_chars must be positive")
        if self.overlap < 0:
            raise ValueError("overlap must be non-negative")
        if self.overlap >= self.max_chars:
            raise ValueError("overlap must be smaller than max_chars")


@dataclass(frozen=True)
class Chunk:
    """A searchable text chunk with full provenance metadata."""

    chunk_id: str
    document_id: str
    text: str
    chunk_index: int
    page_number: int | None
    section: str | None
    source_sha256: str
    document_version: str | None
    source: str
    source_url: str | None
    title: str

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "text": self.text,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "section": self.section,
            "source_sha256": self.source_sha256,
            "document_version": self.document_version,
            "source": self.source,
            "source_url": self.source_url,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Chunk:
        return cls(
            chunk_id=str(data["chunk_id"]),
            document_id=str(data["document_id"]),
            text=str(data["text"]),
            chunk_index=int(data["chunk_index"]),
            page_number=data.get("page_number"),
            section=data.get("section"),
            source_sha256=str(data["source_sha256"]),
            document_version=data.get("document_version"),
            source=str(data["source"]),
            source_url=data.get("source_url"),
            title=str(data["title"]),
        )


@dataclass(frozen=True)
class RetrievedChunk:
    """A ranked search result with similarity score and provenance."""

    chunk: Chunk
    similarity_score: float
    rank: int
