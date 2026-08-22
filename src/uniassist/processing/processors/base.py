"""Processor abstraction for document processing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from uniassist.documents.models import DocumentRecord
from uniassist.processing.models import NormalizedDocument


@dataclass(frozen=True)
class ProcessorContext:
    """Runtime context passed to a document processor."""

    record: DocumentRecord
    output_dir: Path


class DocumentProcessor(Protocol):
    """Transform a source document into normalized content."""

    name: str

    def supports(self, record: DocumentRecord) -> bool:
        """Return True when this processor can handle *record*."""

    def process(self, context: ProcessorContext) -> NormalizedDocument:
        """Process the source document into normalized content."""
