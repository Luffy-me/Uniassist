"""Normalize Appwrite Python SDK 23.x responses for UniAssist persistence."""

from __future__ import annotations

from typing import Any


def sanitize_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Remove null values and coerce values for Appwrite attribute writes."""
    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, bool):
            sanitized[key] = value
        elif isinstance(value, (int, float)):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)
    return sanitized


def document_data(payload: Any) -> dict[str, Any]:
    """Extract user-defined row data from SDK models, dicts, or test doubles."""
    if payload is None:
        return {}
    if isinstance(payload, dict):
        nested = payload.get("data")
        if isinstance(nested, dict):
            return dict(nested)
        return {
            key: value
            for key, value in payload.items()
            if not str(key).startswith("$")
        }
    data = getattr(payload, "data", None)
    if isinstance(data, dict):
        return dict(data)
    if data is not None and hasattr(data, "model_dump"):
        return dict(data.model_dump())
    if hasattr(payload, "model_dump"):
        dumped = payload.model_dump(by_alias=True)
        nested = dumped.get("data")
        if isinstance(nested, dict):
            return dict(nested)
        return {
            key: value
            for key, value in dumped.items()
            if not str(key).startswith("$")
        }
    return {}


def document_id(payload: Any) -> str | None:
    """Return the Appwrite document/row ID from an SDK response."""
    if isinstance(payload, dict):
        return str(payload.get("$id") or payload.get("id") or "") or None
    for attr in ("id",):
        value = getattr(payload, attr, None)
        if value:
            return str(value)
    dumped = document_data(payload)
    return str(dumped.get("document_id") or dumped.get("chunk_id") or "") or None


def appwrite_row_id(key: str) -> str:
    """Map a UniAssist identifier to a valid Appwrite row/document ID."""
    import hashlib
    import re

    if len(key) <= 36 and re.fullmatch(r"[A-Za-z0-9._-]+", key):
        return key
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:36]


def iter_collection_documents(response: Any) -> list[dict[str, Any]]:
    """Return user row payloads from a list-documents SDK response."""
    if isinstance(response, dict):
        items = response.get("documents", [])
    else:
        items = getattr(response, "documents", [])
    return [document_data(item) for item in items]
