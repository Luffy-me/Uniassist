"""Processing models and normalized content representation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class ProcessingStatus(StrEnum):
    """Lifecycle status for document processing."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class NormalizedBlock:
    """A normalized text block suitable for future chunking."""

    text: str
    page_number: int | None = None
    section: str | None = None


@dataclass(frozen=True)
class NormalizedDocument:
    """Normalized structured content derived from a source document."""

    document_id: str
    title: str
    source: str
    source_url: str | None
    source_sha256: str
    processor: str
    processor_version: str | None
    processed_at: datetime
    blocks: list[NormalizedBlock]

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "title": self.title,
            "source": self.source,
            "source_url": self.source_url,
            "source_sha256": self.source_sha256,
            "processor": self.processor,
            "processor_version": self.processor_version,
            "processed_at": self.processed_at.isoformat(),
            "blocks": [
                {
                    "text": block.text,
                    "page_number": block.page_number,
                    "section": block.section,
                }
                for block in self.blocks
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> NormalizedDocument:
        return cls(
            document_id=str(data["document_id"]),
            title=str(data["title"]),
            source=str(data["source"]),
            source_url=data.get("source_url"),
            source_sha256=str(data["source_sha256"]),
            processor=str(data["processor"]),
            processor_version=data.get("processor_version"),
            processed_at=datetime.fromisoformat(str(data["processed_at"])),
            blocks=[
                NormalizedBlock(
                    text=str(block["text"]),
                    page_number=block.get("page_number"),
                    section=block.get("section"),
                )
                for block in data["blocks"]
            ],
        )


@dataclass(frozen=True)
class ProcessingResult:
    """Outcome of a document processing attempt."""

    document_id: str
    status: ProcessingStatus
    processor: str
    input_path: Path
    output_path: Path | None
    processed_at: datetime
    source_sha256: str
    content_hash: str | None = None
    processor_version: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "document_id": self.document_id,
            "status": self.status.value,
            "processor": self.processor,
            "input_path": str(self.input_path),
            "output_path": str(self.output_path) if self.output_path else None,
            "processed_at": self.processed_at.isoformat(),
            "source_sha256": self.source_sha256,
            "content_hash": self.content_hash,
            "processor_version": self.processor_version,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str | None]) -> ProcessingResult:
        output = data.get("output_path")
        return cls(
            document_id=str(data["document_id"]),
            status=ProcessingStatus(str(data["status"])),
            processor=str(data["processor"]),
            input_path=Path(str(data["input_path"])),
            output_path=Path(output) if output else None,
            processed_at=datetime.fromisoformat(str(data["processed_at"])),
            source_sha256=str(data["source_sha256"]),
            content_hash=data.get("content_hash"),
            processor_version=data.get("processor_version"),
            error=data.get("error"),
        )
