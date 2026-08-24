"""Appwrite Database-backed document metadata store."""

from __future__ import annotations

import json
from pathlib import Path

from uniassist.documents.models import DocumentRecord
from uniassist.persistence.appwrite_blob_store import AppwriteBlobStore
from uniassist.persistence.appwrite_client import AppwriteClients
from uniassist.persistence.appwrite_paths import (
    decode_blob_path,
    encode_blob_path,
    is_remote_blob_path,
    normalize_blob_ref,
)
from uniassist.persistence.appwrite_sdk_adapter import (
    document_data,
    iter_collection_documents,
    sanitize_payload,
)


class AppwriteDocumentStore:
    """Document metadata in Appwrite Database with blobs in Storage."""

    def __init__(
        self,
        clients: AppwriteClients,
        *,
        blob_store: AppwriteBlobStore,
    ) -> None:
        self._clients = clients
        self._config = clients.config
        self._blob_store = blob_store

    def save_blob(self, content: bytes, filename: str) -> Path:
        blob_ref = self._blob_store.save(content, filename)
        return encode_blob_path(blob_ref)

    def find_by_sha256(self, digest: str) -> DocumentRecord | None:
        for record in self.list_records():
            if record.sha256 == digest:
                return record
        return None

    def add_record(self, record: DocumentRecord) -> DocumentRecord:
        if self.get(record.document_id) is not None:
            raise ValueError(f"document_id already exists: {record.document_id}")
        self._write_record(record)
        return record

    def update_record(self, record: DocumentRecord) -> DocumentRecord:
        if self.get(record.document_id) is None:
            raise KeyError(f"document not found: {record.document_id}")
        self._write_record(record)
        return record

    def get(self, document_id: str) -> DocumentRecord | None:
        try:
            payload = self._clients.databases.get_document(
                database_id=self._config.database_id,
                collection_id=self._config.documents_collection_id,
                document_id=document_id,
            )
        except Exception:
            return None
        return _record_from_payload(document_data(payload))

    def list_records(self) -> list[DocumentRecord]:
        response = self._clients.databases.list_documents(
            database_id=self._config.database_id,
            collection_id=self._config.documents_collection_id,
        )
        documents = iter_collection_documents(response)
        records = [_record_from_payload(item) for item in documents]
        return sorted(records, key=lambda item: item.uploaded_at)

    def blob_exists(self, record: DocumentRecord) -> bool:
        ref = decode_blob_path(record.storage_ref or record.local_path)
        return self._blob_store.exists(ref)

    def read_blob(self, record: DocumentRecord) -> bytes:
        ref = decode_blob_path(record.storage_ref or record.local_path)
        return self._blob_store.read(ref)

    def _write_record(self, record: DocumentRecord) -> None:
        payload = sanitize_payload(record.to_dict())
        payload["metadata_json"] = json.dumps(record.to_dict(), ensure_ascii=False)
        try:
            self._clients.databases.create_document(
                database_id=self._config.database_id,
                collection_id=self._config.documents_collection_id,
                document_id=record.document_id,
                data=payload,
            )
        except Exception:
            self._clients.databases.update_document(
                database_id=self._config.database_id,
                collection_id=self._config.documents_collection_id,
                document_id=record.document_id,
                data=payload,
            )


def _record_from_payload(payload: dict) -> DocumentRecord:
    if "metadata_json" in payload:
        data = json.loads(str(payload["metadata_json"]))
    else:
        data = dict(payload)
    record = DocumentRecord.from_dict(data)
    return _repair_record_paths(record)


def _repair_record_paths(record: DocumentRecord) -> DocumentRecord:
    storage_ref = record.storage_ref
    local_path = record.local_path
    if storage_ref:
        storage_ref = normalize_blob_ref(storage_ref)
    elif is_remote_blob_path(local_path):
        storage_ref = decode_blob_path(local_path)
    else:
        local_text = str(local_path)
        if local_text.startswith("appwrite:"):
            storage_ref = normalize_blob_ref(local_text)
            local_path = encode_blob_path(storage_ref)
    if storage_ref and not is_remote_blob_path(local_path):
        local_path = encode_blob_path(storage_ref)
    if storage_ref == record.storage_ref and local_path == record.local_path:
        return record
    return DocumentRecord(
        document_id=record.document_id,
        title=record.title,
        filename=record.filename,
        content_type=record.content_type,
        sha256=record.sha256,
        local_path=local_path,
        uploaded_at=record.uploaded_at,
        source=record.source,
        source_type=record.source_type,
        source_url=record.source_url,
        effective_date=record.effective_date,
        version=record.version,
        status=record.status,
        verification_state=record.verification_state,
        notes=record.notes,
        storage_ref=storage_ref,
    )
