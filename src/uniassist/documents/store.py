"""Document store abstraction and JSON-backed implementation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

from uniassist.core.hashing import sha256_hex
from uniassist.documents.models import DocumentRecord


class DocumentStore(Protocol):
    """Interface for persisting corpus blobs and metadata."""

    def save_blob(self, content: bytes, filename: str) -> Path:
        """Persist immutable content and return the blob path."""

    def find_by_sha256(self, digest: str) -> DocumentRecord | None:
        """Return an existing record for *digest*, if present."""

    def add_record(self, record: DocumentRecord) -> DocumentRecord:
        """Add a new record to the index."""

    def update_record(self, record: DocumentRecord) -> DocumentRecord:
        """Replace an existing record in the index."""

    def get(self, document_id: str) -> DocumentRecord | None:
        """Return a record by ID."""

    def list_records(self) -> list[DocumentRecord]:
        """Return all records in stable upload order."""

    def blob_exists(self, record: DocumentRecord) -> bool:
        """Return whether the record's blob is available."""

    def read_blob(self, record: DocumentRecord) -> bytes:
        """Read the record's blob bytes."""


class JsonDocumentStore:
    """Filesystem blob store with a JSON metadata index."""

    def __init__(
        self,
        raw_dir: Path,
        index_path: Path,
        *,
        blob_store: object | None = None,
    ) -> None:
        self.raw_dir = raw_dir
        self.index_path = index_path
        if blob_store is None:
            from uniassist.persistence.blob_store import LocalBlobStore

            blob_store = LocalBlobStore(raw_dir)
        self._blob_store = blob_store
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._write_index([])

    def save_blob(self, content: bytes, filename: str) -> Path:
        digest = sha256_hex(content)
        blob_ref = self._blob_store.save(content, filename, digest=digest)
        return Path(blob_ref)

    def find_by_sha256(self, digest: str) -> DocumentRecord | None:
        for record in self.list_records():
            if record.sha256 == digest:
                return record
        return None

    def add_record(self, record: DocumentRecord) -> DocumentRecord:
        records = self.list_records()
        if any(item.document_id == record.document_id for item in records):
            raise ValueError(f"document_id already exists: {record.document_id}")
        records.append(record)
        self._write_index(records)
        return record

    def update_record(self, record: DocumentRecord) -> DocumentRecord:
        records = self.list_records()
        updated: list[DocumentRecord] = []
        found = False
        for item in records:
            if item.document_id == record.document_id:
                updated.append(record)
                found = True
            else:
                updated.append(item)
        if not found:
            raise KeyError(f"document not found: {record.document_id}")
        self._write_index(updated)
        return record

    def get(self, document_id: str) -> DocumentRecord | None:
        for record in self.list_records():
            if record.document_id == document_id:
                return record
        return None

    def list_records(self) -> list[DocumentRecord]:
        if not self.index_path.exists():
            return []
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        return [DocumentRecord.from_dict(item) for item in data]

    def blob_exists(self, record: DocumentRecord) -> bool:
        ref = record.storage_ref or str(record.local_path)
        return self._blob_store.exists(ref)

    def read_blob(self, record: DocumentRecord) -> bytes:
        ref = record.storage_ref or str(record.local_path)
        return self._blob_store.read(ref)

    def _write_index(self, records: list[DocumentRecord]) -> None:
        payload = [record.to_dict() for record in records]
        temp_path = self.index_path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, self.index_path)
