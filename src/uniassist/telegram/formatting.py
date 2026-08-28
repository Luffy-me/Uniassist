"""Telegram message formatting helpers."""

from __future__ import annotations

import re

from uniassist.telegram.api_client import AskResult, CitationPayload
from uniassist.telegram.errors import REFUSAL_MESSAGE

TELEGRAM_HARD_LIMIT = 4096
SOURCES_HEADING = "Sources / Источники:"


def format_citation(citation: CitationPayload) -> str:
    """Format one citation line without inventing metadata."""
    if citation.label.strip():
        line = f"• {citation.label.strip()}"
    else:
        parts = [citation.title.strip() or "Document"]
        if citation.page_number is not None:
            parts.append(f"p. {citation.page_number}")
        elif citation.section:
            parts.append(f"§{citation.section}")
        line = f"• {' — '.join(parts)}"
    source_url = (citation.source_url or "").strip()
    if source_url:
        return f"{line}\n  {source_url}"
    return line


def format_ask_result(result: AskResult) -> str:
    """Convert an AskResult into plain text for Telegram."""
    if result.status == "verified" and result.answer:
        lines = [result.answer.strip()]
        if result.citations:
            lines.append("")
            lines.append(SOURCES_HEADING)
            lines.extend(format_citation(item) for item in result.citations)
        return "\n".join(lines).strip()

    return REFUSAL_MESSAGE


def split_message(text: str, *, max_length: int) -> list[str]:
    """Split long answers without silently truncating content."""
    cleaned = text.strip()
    if not cleaned:
        return [""]
    if len(cleaned) <= max_length:
        return [cleaned]

    chunks: list[str] = []
    remaining = cleaned
    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break
        split_at = _choose_split_index(remaining, max_length)
        chunk = remaining[:split_at].rstrip()
        if not chunk:
            chunk = remaining[:max_length]
            split_at = max_length
        chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()
    return chunks


def sanitize_plain_text(text: str) -> str:
    """Use plain text safe for Telegram without Markdown parsing issues."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _choose_split_index(text: str, max_length: int) -> int:
    window = text[:max_length]
    for separator in ("\n\n", "\n", ". ", " "):
        index = window.rfind(separator)
        if index > max_length // 3:
            return index + len(separator)
    return max_length


def escape_markdown(text: str) -> str:
    """Escape Telegram legacy Markdown special characters."""
    return re.sub(r"([_*`\[])", r"\\\1", text)
