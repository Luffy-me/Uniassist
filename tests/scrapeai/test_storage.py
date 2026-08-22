"""Tests for local document storage."""

from __future__ import annotations

from pathlib import Path

import pytest

from uniassist.scrapeai.storage import DocumentStorage, StorageConflictError


def test_storage_persists_content(tmp_path: Path) -> None:
    storage = DocumentStorage(tmp_path)
    path = storage.store(b"pdf-bytes", "report.pdf")
    assert path.exists()
    assert path.read_bytes() == b"pdf-bytes"


def test_storage_returns_existing_path_for_same_hash(tmp_path: Path) -> None:
    storage = DocumentStorage(tmp_path)
    first = storage.store(b"same-content", "first.pdf")
    second = storage.store(b"same-content", "second.pdf")
    assert first == second


def test_storage_refuses_to_overwrite_different_content(tmp_path: Path) -> None:
    from uniassist.scrapeai.hashing import sha256_hex

    storage = DocumentStorage(tmp_path)
    content = b"different"
    digest = sha256_hex(content)
    destination = tmp_path / f"{digest}__report.pdf"
    destination.write_bytes(b"original")

    with pytest.raises(StorageConflictError):
        storage.store(content, "report.pdf")
