"""Tests for processor routing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tests.processing.conftest import build_record
from uniassist.processing.processors.mineru import MinerUProcessor
from uniassist.processing.processors.pdf_text import PdfTextProcessor
from uniassist.processing.processors.text import TextProcessor
from uniassist.processing.router import ProcessorRouter, UnsupportedDocumentError


def test_router_selects_mineru_for_pdf_when_available() -> None:
    record = build_record(
        document_id="pdf-1",
        filename="rules.pdf",
        local_path=Path("rules.pdf"),
        sha256="sha",
    )
    with patch(
        "uniassist.processing.processors.mineru.mineru_available",
        return_value=True,
    ):
        router = ProcessorRouter()
        processor = router.select(record)
    assert isinstance(processor, MinerUProcessor)


def test_router_selects_pdf_text_when_mineru_unavailable() -> None:
    record = build_record(
        document_id="pdf-1",
        filename="rules.pdf",
        local_path=Path("rules.pdf"),
        sha256="sha",
    )
    with patch(
        "uniassist.processing.processors.mineru.mineru_available",
        return_value=False,
    ):
        router = ProcessorRouter()
        processor = router.select(record)
    assert isinstance(processor, PdfTextProcessor)


def test_router_selects_text_for_txt() -> None:
    record = build_record(
        document_id="txt-1",
        filename="notes.txt",
        local_path=Path("notes.txt"),
        sha256="sha",
    )
    router = ProcessorRouter()
    processor = router.select(record)
    assert isinstance(processor, TextProcessor)


def test_router_rejects_unsupported_extension() -> None:
    record = build_record(
        document_id="html-1",
        filename="page.html",
        local_path=Path("page.html"),
        sha256="sha",
    )
    router = ProcessorRouter()
    with pytest.raises(UnsupportedDocumentError, match="no processor available"):
        router.select(record)
