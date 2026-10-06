"""Dependency-free DOCX text extraction."""

from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

from uniassist.documents.models import DocumentRecord
from uniassist.processing.models import NormalizedBlock, NormalizedDocument
from uniassist.processing.processors.base import ProcessorContext

PROCESSOR_VERSION = "1.0.0"
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MAX_XML_BYTES = 100 * 1024 * 1024


class InvalidDocxError(ValueError):
    """Raised when a file is not a readable DOCX document."""


class EmptyDocxError(ValueError):
    """Raised when a DOCX contains no extractable text."""


class DocxTextProcessor:
    """Extract paragraph text from DOCX files using only the standard library."""

    name = "docx_text"

    def supports(self, record: DocumentRecord) -> bool:
        return record.filename.lower().endswith(".docx")

    def process(self, context: ProcessorContext) -> NormalizedDocument:
        record = context.record
        paragraphs = _read_paragraphs(context.source_path)
        if not paragraphs:
            raise EmptyDocxError("DOCX contains no extractable text")
        return NormalizedDocument(
            document_id=record.document_id,
            title=record.title,
            source=record.source,
            source_url=record.source_url,
            source_sha256=record.sha256,
            processor=self.name,
            processor_version=PROCESSOR_VERSION,
            processed_at=datetime.now(UTC),
            blocks=[
                NormalizedBlock(
                    text=text,
                    page_number=None,
                    section=f"paragraph_{index + 1}",
                )
                for index, text in enumerate(paragraphs)
            ],
        )


def _read_paragraphs(path: Path) -> list[str]:
    try:
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > _MAX_XML_BYTES:
                raise InvalidDocxError("DOCX body is too large to process")
            xml_bytes = archive.read(info)
    except (zipfile.BadZipFile, KeyError) as exc:
        raise InvalidDocxError("file is not a valid DOCX document") from exc
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise InvalidDocxError("DOCX body is not valid XML") from exc

    paragraphs: list[str] = []
    for paragraph in root.iter(f"{_W}p"):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{_W}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{_W}tab":
                parts.append("\t")
            elif node.tag in (f"{_W}br", f"{_W}cr"):
                parts.append("\n")
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return paragraphs
