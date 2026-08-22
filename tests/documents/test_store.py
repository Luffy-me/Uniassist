"""Tests for document store behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from uniassist.core.hashing import sha256_hex
from uniassist.documents.models import (
    DocumentRecord,
    DocumentStatus,
    SourceType,
    VerificationState,
)
from uniassist.documents.store import JsonDocumentStore, StorageConflictError


def _sample_record(tmp_path: Path, document_id: str, digest: str) -> DocumentRecord:
    from datetime import UTC, datetime

    blob = tmp_path / "raw" / f"{digest}__sample.pdf"
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(b"%PDF-1.4")
    return DocumentRecord(
        document_id=document_id,
        title="Sample",
        filename="sample.pdf",
        content_type="application/pdf",
        sha256=digest,
        local_path=blob,
        uploaded_at=datetime.now(UTC),
        source="test",
        source_type=SourceType.ADMIN_UPLOAD,
        status=DocumentStatus.DRAFT,
        verification_state=VerificationState.PENDING,
    )


def test_immutable_storage_writes_hash_prefixed_blob(tmp_path: Path) -> None:
    store = JsonDocumentStore(
        raw_dir=tmp_path / "raw",
        index_path=tmp_path / "metadata" / "documents.json",
    )
    content = b"%PDF-1.4 test"
    path = store.save_blob(content, "rules.pdf")
    assert path.name.startswith(sha256_hex(content))
    assert path.read_bytes() == content


def test_duplicate_content_returns_existing_blob(tmp_path: Path) -> None:
    store = JsonDocumentStore(
        raw_dir=tmp_path / "raw",
        index_path=tmp_path / "metadata" / "documents.json",
    )
    first = store.save_blob(b"same-content", "first.pdf")
    second = store.save_blob(b"same-content", "second.pdf")
    assert first == second


def test_different_content_does_not_overwrite_existing_blob(tmp_path: Path) -> None:
    store = JsonDocumentStore(
        raw_dir=tmp_path / "raw",
        index_path=tmp_path / "metadata" / "documents.json",
    )
    content = b"different"
    digest = sha256_hex(content)
    destination = tmp_path / "raw" / f"{digest}__report.pdf"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"original")

    with pytest.raises(StorageConflictError):
        store.save_blob(content, "report.pdf")


def test_json_index_persistence_round_trip(tmp_path: Path) -> None:
    store = JsonDocumentStore(
        raw_dir=tmp_path / "raw",
        index_path=tmp_path / "metadata" / "documents.json",
    )
    record = _sample_record(tmp_path, "doc-1", sha256_hex(b"%PDF-1.4"))
    store.add_record(record)

    reloaded = JsonDocumentStore(
        raw_dir=tmp_path / "raw",
        index_path=tmp_path / "metadata" / "documents.json",
    )
    loaded = reloaded.get("doc-1")
    assert loaded is not None
    assert loaded.title == "Sample"
    assert loaded.status == DocumentStatus.DRAFT
