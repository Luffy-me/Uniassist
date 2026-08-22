"""Plain-text document processor."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from uniassist.documents.models import DocumentRecord
from uniassist.processing.models import NormalizedBlock, NormalizedDocument
from uniassist.processing.processors.base import ProcessorContext

PROCESSOR_VERSION = "1.0.0"


class TextProcessor:
    """Process UTF-8 text files without external tooling."""

    name = "text"

    def supports(self, record: DocumentRecord) -> bool:
        return Path(record.filename).suffix.lower() == ".txt"

    def process(self, context: ProcessorContext) -> NormalizedDocument:
        record = context.record
        text = context.source_path.read_text(encoding="utf-8")
        paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
        if not paragraphs:
            paragraphs = [text.strip()] if text.strip() else [""]

        blocks = [
            NormalizedBlock(
                text=paragraph,
                page_number=1,
                section=f"paragraph_{index + 1}",
            )
            for index, paragraph in enumerate(paragraphs)
        ]
        return NormalizedDocument(
            document_id=record.document_id,
            title=record.title,
            source=record.source,
            source_url=record.source_url,
            source_sha256=record.sha256,
            processor=self.name,
            processor_version=PROCESSOR_VERSION,
            processed_at=datetime.now(UTC),
            blocks=blocks,
        )
