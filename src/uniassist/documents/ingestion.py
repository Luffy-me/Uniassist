"""Document ingestion service for admin-controlled uploads."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from uniassist.core.hashing import sha256_hex
from uniassist.documents.models import (
    DocumentRecord,
    DocumentStatus,
    SourceType,
    VerificationState,
)
from uniassist.documents.store import DocumentStore, JsonDocumentStore
from uniassist.documents.validation import validate_upload


@dataclass(frozen=True)
class IngestResult:
    """Outcome of an ingestion attempt."""

    record: DocumentRecord
    duplicate: bool


@dataclass(frozen=True)
class IngestRequest:
    """Metadata supplied when ingesting a document."""

    title: str
    source: str
    source_type: SourceType = SourceType.ADMIN_UPLOAD
    source_url: str | None = None
    effective_date: date | None = None
    version: str | None = None
    notes: str | None = None


class DocumentIngestionService:
    """Validate, store, and index authoritative documents."""

    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    @classmethod
    def default(cls, project_root: Path | None = None) -> DocumentIngestionService:
        root = project_root or Path.cwd()
        store = JsonDocumentStore(
            raw_dir=root / "data" / "raw",
            index_path=root / "data" / "metadata" / "documents.json",
        )
        return cls(store)

    def ingest_file(self, path: Path, request: IngestRequest) -> IngestResult:
        content = path.read_bytes()
        return self.ingest_bytes(
            filename=path.name,
            content=content,
            request=request,
        )

    def ingest_bytes(
        self,
        *,
        filename: str,
        content: bytes,
        request: IngestRequest,
    ) -> IngestResult:
        if request.source_type != SourceType.ADMIN_UPLOAD:
            raise ValueError(
                "only admin_upload is supported in Phase 3; "
                f"got {request.source_type.value}"
            )

        validation = validate_upload(filename, content)
        if not validation.success:
            raise ValueError("; ".join(validation.errors))

        digest = sha256_hex(content)
        existing = self._store.find_by_sha256(digest)
        if existing is not None:
            return IngestResult(record=existing, duplicate=True)

        blob_path = self._store.save_blob(content, filename)
        record = DocumentRecord(
            document_id=str(uuid.uuid4()),
            title=request.title,
            filename=Path(filename).name,
            content_type=validation.content_type or "application/octet-stream",
            sha256=digest,
            local_path=blob_path,
            uploaded_at=datetime.now(UTC),
            source=request.source,
            source_type=request.source_type,
            source_url=request.source_url,
            effective_date=request.effective_date,
            version=request.version,
            status=DocumentStatus.DRAFT,
            verification_state=VerificationState.PENDING,
            notes=request.notes,
        )
        saved = self._store.add_record(record)
        return IngestResult(record=saved, duplicate=False)

    def activate(self, document_id: str) -> DocumentRecord:
        """Mark a document verified and active through explicit admin action."""
        record = self._require_record(document_id)
        if record.status == DocumentStatus.ACTIVE:
            return record
        if record.status == DocumentStatus.ARCHIVED:
            raise ValueError("archived documents cannot be activated")
        updated = DocumentRecord(
            document_id=record.document_id,
            title=record.title,
            filename=record.filename,
            content_type=record.content_type,
            sha256=record.sha256,
            local_path=record.local_path,
            uploaded_at=record.uploaded_at,
            source=record.source,
            source_type=record.source_type,
            source_url=record.source_url,
            effective_date=record.effective_date,
            version=record.version,
            status=DocumentStatus.ACTIVE,
            verification_state=VerificationState.VERIFIED,
            notes=record.notes,
        )
        return self._store.update_record(updated)

    def list_documents(self) -> list[DocumentRecord]:
        return self._store.list_records()

    def get_document(self, document_id: str) -> DocumentRecord | None:
        return self._store.get(document_id)

    def _require_record(self, document_id: str) -> DocumentRecord:
        record = self._store.get(document_id)
        if record is None:
            raise KeyError(f"document not found: {document_id}")
        return record
