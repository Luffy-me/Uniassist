"""Tests for deterministic chunking."""

from __future__ import annotations

from datetime import UTC, datetime

from uniassist.processing.models import NormalizedBlock, NormalizedDocument
from uniassist.rag.chunking import chunk_document, make_chunk_id
from uniassist.rag.models import ChunkConfig


def _normalized(blocks: list[tuple[str, int | None, str | None]]) -> NormalizedDocument:
    return NormalizedDocument(
        document_id="doc-1",
        title="Rules",
        source="Registrar",
        source_url="https://example.org/rules",
        source_sha256="abc123",
        processor="text",
        processor_version="1.0.0",
        processed_at=datetime.now(UTC),
        blocks=[
            NormalizedBlock(text=text, page_number=page, section=section)
            for text, page, section in blocks
        ],
    )


def test_chunking_is_deterministic() -> None:
    document = _normalized(
        [
            ("Students may request academic leave by submitting a form.", 1, "1.1"),
            ("Library opening hours are posted online.", 2, "2.1"),
        ]
    )
    first = chunk_document(document, ChunkConfig(max_chars=80, overlap=10))
    second = chunk_document(document, ChunkConfig(max_chars=80, overlap=10))
    assert first == second


def test_chunk_ids_are_deterministic() -> None:
    chunk_id = make_chunk_id("doc-1", "abc123", 0, "hello")
    assert chunk_id == make_chunk_id("doc-1", "abc123", 0, "hello")
    assert chunk_id != make_chunk_id("doc-1", "abc123", 1, "hello")


def test_ordering_and_metadata_are_preserved() -> None:
    chunks = chunk_document(
        _normalized(
            [
                ("First paragraph on page one.", 1, "intro"),
                ("Second paragraph on page two.", 2, "details"),
            ]
        ),
        ChunkConfig(max_chars=200, overlap=0),
    )
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert chunks[0].page_number == 1
    assert chunks[0].section == "intro"
    assert chunks[-1].page_number == 2


def test_long_text_is_split_with_overlap() -> None:
    long_text = " ".join(["word"] * 120)
    chunks = chunk_document(
        _normalized([(long_text, 3, "long-section")]),
        ChunkConfig(max_chars=100, overlap=20),
    )
    assert len(chunks) > 1
    assert all(chunk.text for chunk in chunks)
    assert all(chunk.page_number == 3 for chunk in chunks)


def test_no_empty_chunks() -> None:
    chunks = chunk_document(
        _normalized([("   ", 1, "empty"), ("Actual content here.", 1, "real")]),
        ChunkConfig(max_chars=50, overlap=0),
    )
    assert len(chunks) == 1
    assert chunks[0].text == "Actual content here."
