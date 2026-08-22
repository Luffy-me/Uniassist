"""Appwrite Storage-backed blob store."""

from __future__ import annotations

import io
from dataclasses import dataclass

from uniassist.core.hashing import sha256_hex
from uniassist.documents.validation import sanitize_filename
from uniassist.persistence.appwrite_client import AppwriteClients
from uniassist.persistence.blob_store import DocumentBlobStore


@dataclass
class AppwriteBlobStore:
    """Immutable blob storage in an Appwrite bucket."""

    clients: AppwriteClients
    bucket_id: str
    ref_prefix: str

    def save(self, content: bytes, filename: str, *, digest: str | None = None) -> str:
        resolved_digest = digest or sha256_hex(content)
        file_id = _file_id_for_digest(resolved_digest)
        blob_ref = _blob_ref(self.ref_prefix, self.bucket_id, file_id)
        if self.exists(blob_ref):
            return blob_ref

        safe_name = sanitize_filename(filename)
        payload = io.BytesIO(content)
        self.clients.storage.create_file(
            bucket_id=self.bucket_id,
            file_id=file_id,
            file=(safe_name, payload),
        )
        return blob_ref

    def read(self, blob_ref: str) -> bytes:
        bucket_id, file_id = _parse_blob_ref(blob_ref)
        return self.clients.storage.get_file_download(bucket_id, file_id)

    def exists(self, blob_ref: str) -> bool:
        bucket_id, file_id = _parse_blob_ref(blob_ref)
        try:
            self.clients.storage.get_file(bucket_id, file_id)
            return True
        except Exception:
            return False

    def delete(self, blob_ref: str) -> None:
        bucket_id, file_id = _parse_blob_ref(blob_ref)
        try:
            self.clients.storage.delete_file(bucket_id, file_id)
        except Exception:
            return


def _file_id_for_digest(digest: str) -> str:
    return digest[:32]


def _blob_ref(prefix: str, bucket_id: str, file_id: str) -> str:
    return f"appwrite://{prefix}/{bucket_id}/{file_id}"


def _parse_blob_ref(blob_ref: str) -> tuple[str, str]:
    if not blob_ref.startswith("appwrite://"):
        raise ValueError(f"invalid Appwrite blob reference: {blob_ref}")
    parts = blob_ref.removeprefix("appwrite://").split("/")
    if len(parts) != 3:
        raise ValueError(f"invalid Appwrite blob reference: {blob_ref}")
    _, bucket_id, file_id = parts
    return bucket_id, file_id


def as_document_blob_store(store: AppwriteBlobStore) -> DocumentBlobStore:
    return store
