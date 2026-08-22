"""Deterministic chunking of normalized documents."""

from __future__ import annotations

import re

from uniassist.core.hashing import sha256_hex
from uniassist.processing.models import NormalizedBlock, NormalizedDocument
from uniassist.rag.models import Chunk, ChunkConfig

_WORD_PATTERN = re.compile(r"\S+")


def make_chunk_id(
    document_id: str,
    source_sha256: str,
    chunk_index: int,
    text: str,
) -> str:
    """Return a deterministic chunk identifier."""
    payload = f"{document_id}:{source_sha256}:{chunk_index}:{text}"
    return sha256_hex(payload.encode("utf-8"))


def chunk_document(
    normalized: NormalizedDocument,
    config: ChunkConfig | None = None,
) -> list[Chunk]:
    """Split a normalized document into ordered, deterministic chunks."""
    cfg = config or ChunkConfig()
    segments = _segments_from_blocks(normalized.blocks)
    raw_chunks = _chunk_segments(segments, cfg)
    return [
        Chunk(
            chunk_id=make_chunk_id(
                normalized.document_id,
                normalized.source_sha256,
                index,
                text,
            ),
            document_id=normalized.document_id,
            text=text,
            chunk_index=index,
            page_number=page_number,
            section=section,
            source_sha256=normalized.source_sha256,
            document_version=None,
            source=normalized.source,
            source_url=normalized.source_url,
            title=normalized.title,
        )
        for index, (text, page_number, section) in enumerate(raw_chunks)
    ]


def _segments_from_blocks(
    blocks: list[NormalizedBlock],
) -> list[tuple[str, int | None, str | None]]:
    segments: list[tuple[str, int | None, str | None]] = []
    for block in blocks:
        text = block.text.strip()
        if not text:
            continue
        segments.append((text, block.page_number, block.section))
    return segments


def _chunk_segments(
    segments: list[tuple[str, int | None, str | None]],
    config: ChunkConfig,
) -> list[tuple[str, int | None, str | None]]:
    chunks: list[tuple[str, int | None, str | None]] = []
    for text, page_number, section in segments:
        if len(text) <= config.max_chars:
            chunks.append((text, page_number, section))
            continue
        for part in _split_text(text, config):
            chunks.append((part, page_number, section))
    return chunks


def _split_text(text: str, config: ChunkConfig) -> list[str]:
    """Split long text preferring paragraph, sentence, then word boundaries."""
    units = _semantic_units(text)
    return _pack_units(units, config)


def _semantic_units(text: str) -> list[str]:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    if len(paragraphs) > 1:
        return paragraphs

    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [part.strip() for part in sentences if part.strip()]
    if len(sentences) > 1:
        return sentences

    return _WORD_PATTERN.findall(text)


def _pack_units(units: list[str], config: ChunkConfig) -> list[str]:
    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for unit in units:
        candidate = unit if not current else f"{current} {unit}"
        if len(candidate) <= config.max_chars:
            current = candidate
            continue

        if current:
            flush()

        if len(unit) <= config.max_chars:
            current = unit
            continue

        for word_chunk in _split_by_words(unit, config):
            chunks.append(word_chunk)

    flush()
    return _apply_overlap(chunks, config.overlap)


def _split_by_words(text: str, config: ChunkConfig) -> list[str]:
    words = _WORD_PATTERN.findall(text)
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= config.max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = word
    if current:
        chunks.append(current)
    return _apply_overlap(chunks, config.overlap)


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    if overlap <= 0 or len(chunks) <= 1:
        return chunks

    merged: list[str] = [chunks[0]]
    for chunk in chunks[1:]:
        previous = merged[-1]
        prefix = previous[-overlap:] if len(previous) > overlap else previous
        if chunk.startswith(prefix):
            merged.append(chunk)
        else:
            merged.append(f"{prefix} {chunk}".strip())
    return merged
