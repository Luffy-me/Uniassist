"""Conservative text extraction for PDFs when MinerU is unavailable."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from uniassist.documents.models import DocumentRecord
from uniassist.processing.models import NormalizedBlock, NormalizedDocument
from uniassist.processing.processors.base import ProcessorContext

PROCESSOR_VERSION = "1.0.0"
MIN_EXTRACTED_CHARS = 20

EMPTY_PDF_MESSAGE = (
    "This PDF has no extractable text (it may be scanned or image-only). "
    "Install MinerU for OCR-capable processing, or upload a text-based PDF."
)


class EmptyPdfTextError(ValueError):
    """Raised when a PDF has no usable extractable text."""


class PdfTextProcessor:
    """Extract embedded text from a PDF without OCR."""

    name = "pdf_text"

    def supports(self, record: DocumentRecord) -> bool:
        return Path(record.filename).suffix.lower() == ".pdf"

    def process(self, context: ProcessorContext) -> NormalizedDocument:
        record = context.record
        try:
            reader = PdfReader(context.source_path)
        except PdfReadError as exc:
            raise EmptyPdfTextError(
                f"{EMPTY_PDF_MESSAGE} PDF could not be read: {exc}"
            ) from exc

        blocks: list[NormalizedBlock] = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            blocks.append(
                NormalizedBlock(
                    text=text,
                    page_number=index,
                    section=f"page_{index}",
                )
            )

        extracted = " ".join(block.text for block in blocks).strip()
        if len(extracted) < MIN_EXTRACTED_CHARS:
            raise EmptyPdfTextError(EMPTY_PDF_MESSAGE)

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
