"""Appwrite-backed index manifest store."""

from __future__ import annotations

import json

from uniassist.persistence.appwrite_client import AppwriteClients
from uniassist.persistence.appwrite_sdk_adapter import document_data, sanitize_payload
from uniassist.rag.index_metadata import IndexManifest

MANIFEST_DOCUMENT_ID = "index_manifest"


class AppwriteIndexManifestStore:
    """Persist vector index manifest metadata in Appwrite Database."""

    def __init__(self, clients: AppwriteClients) -> None:
        self._clients = clients
        self._config = clients.config

    def load(self) -> IndexManifest | None:
        try:
            payload = self._clients.databases.get_document(
                database_id=self._config.database_id,
                collection_id=self._config.chunks_collection_id,
                document_id=MANIFEST_DOCUMENT_ID,
            )
        except Exception:
            return None
        raw = document_data(payload).get("manifest_json")
        if not raw:
            return None
        return IndexManifest.from_dict(json.loads(str(raw)))

    def save(self, manifest: IndexManifest) -> None:
        data = sanitize_payload(
            {
                "chunk_id": MANIFEST_DOCUMENT_ID,
                "document_id": "__manifest__",
                "text": "__manifest__",
                "chunk_index": -1,
                "source_sha256": "__manifest__",
                "embedding": "[]",
                "chunk_json": "{}",
                "manifest_json": json.dumps(manifest.to_dict(), ensure_ascii=False),
            }
        )
        try:
            self._clients.databases.create_document(
                database_id=self._config.database_id,
                collection_id=self._config.chunks_collection_id,
                document_id=MANIFEST_DOCUMENT_ID,
                data=data,
            )
        except Exception:
            self._clients.databases.update_document(
                database_id=self._config.database_id,
                collection_id=self._config.chunks_collection_id,
                document_id=MANIFEST_DOCUMENT_ID,
                data=data,
            )

    def clear(self) -> None:
        try:
            self._clients.databases.delete_document(
                database_id=self._config.database_id,
                collection_id=self._config.chunks_collection_id,
                document_id=MANIFEST_DOCUMENT_ID,
            )
        except Exception:
            return
