"""Processor selection for document processing."""

from __future__ import annotations

from pathlib import Path

from uniassist.documents.models import DocumentRecord
from uniassist.processing.processors.base import DocumentProcessor
from uniassist.processing.processors.mineru import (
    MinerUProcessor,
    mineru_available,
    mineru_supports_docx,
)
from uniassist.processing.processors.text import TextProcessor


class ProcessorRouter:
    """Select the appropriate processor for a document record."""

    def __init__(
        self,
        processors: list[DocumentProcessor] | None = None,
    ) -> None:
        self._processors = processors or [MinerUProcessor(), TextProcessor()]

    def select(self, record: DocumentRecord) -> DocumentProcessor:
        for processor in self._processors:
            if processor.supports(record):
                return processor
        raise UnsupportedDocumentError(
            f"no processor available for file type: {Path(record.filename).suffix}"
        )

    def docx_status(self, record: DocumentRecord) -> str:
        """Describe whether DOCX can be processed in the current environment."""
        if Path(record.filename).suffix.lower() != ".docx":
            return "not_docx"
        if not mineru_available():
            return "mineru_not_installed"
        if not mineru_supports_docx():
            return "docx_deferred"
        return "mineru_docx_available"


class UnsupportedDocumentError(Exception):
    """Raised when no processor can handle a document."""
