"""Appwrite Database-backed vector store."""

from __future__ import annotations

import json
import time

from appwrite.query import Query

from uniassist.persistence.appwrite_client import AppwriteClients
from uniassist.persistence.appwrite_sdk_adapter import (
    appwrite_row_id,
    iter_collection_documents,
    sanitize_payload,
)
from uniassist.rag.models import Chunk
from uniassist.rag.vector_store import VectorStore

APPWRITE_PAGE_SIZE = 100
APPWRITE_READ_RETRIES = 3


class AppwriteVectorStore(VectorStore):
    """Persist chunk embeddings in Appwrite and search in-memory."""

    def __init__(self, clients: AppwriteClients) -> None:
        super().__init__()
        self._clients = clients
        self._config = clients.config
        self._load()

    def add(self, chunk: Chunk, vector: list[float]) -> None:
        super().add(chunk, vector)
        self._persist_chunk(chunk, vector)

    def delete(self, chunk_id: str) -> None:
        super().delete(chunk_id)
        try:
            self._clients.databases.delete_document(
                database_id=self._config.database_id,
                collection_id=self._config.chunks_collection_id,
                document_id=appwrite_row_id(chunk_id),
            )
        except Exception:
            return

    def delete_document(self, document_id: str) -> int:
        removed = 0
        for chunk_id, chunk in list(self._chunks.items()):
            if chunk.document_id == document_id:
                self.delete(chunk_id)
                removed += 1
        return removed

    def clear(self) -> None:
        chunk_ids = list(self._chunks)
        for chunk_id in chunk_ids:
            self.delete(chunk_id)
        self._wait_for_remote_deletions(chunk_ids)
        super().clear()

    def _wait_for_remote_deletions(self, chunk_ids: list[str]) -> None:
        """Avoid rebuilding against Appwrite rows that are still deleting."""
        for _ in range(20):
            remaining = []
            for chunk_id in chunk_ids:
                try:
                    self._clients.databases.get_document(
                        database_id=self._config.database_id,
                        collection_id=self._config.chunks_collection_id,
                        document_id=appwrite_row_id(chunk_id),
                    )
                except Exception:
                    continue
                remaining.append(chunk_id)
            if not remaining:
                return
            time.sleep(0.5)
        raise RuntimeError("Appwrite chunk deletion did not complete before rebuild")

    def _persist_chunk(self, chunk: Chunk, vector: list[float]) -> None:
        payload = sanitize_payload(
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "text": chunk.text,
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "section": chunk.section,
                "source_sha256": chunk.source_sha256,
                "document_version": chunk.document_version,
                "source": chunk.source,
                "source_url": chunk.source_url,
                "title": chunk.title,
                "embedding": _serialize_vector(vector),
                "chunk_json": json.dumps(chunk.to_dict(), ensure_ascii=False),
            }
        )
        try:
            self._clients.databases.create_document(
                database_id=self._config.database_id,
                collection_id=self._config.chunks_collection_id,
                document_id=appwrite_row_id(chunk.chunk_id),
                data=payload,
            )
        except Exception:
            self._clients.databases.update_document(
                database_id=self._config.database_id,
                collection_id=self._config.chunks_collection_id,
                document_id=appwrite_row_id(chunk.chunk_id),
                data=payload,
            )

    def _load(self) -> None:
        offset = 0
        while True:
            response = self._load_page(offset)
            items = iter_collection_documents(response)
            for item in items:
                if item.get("chunk_id") == "index_manifest":
                    continue
                chunk_data = json.loads(str(item.get("chunk_json", "{}")))
                if not chunk_data:
                    continue
                chunk = Chunk.from_dict(chunk_data)
                vector = json.loads(str(item.get("embedding", "[]")))
                if vector:
                    super().add(chunk, vector)
            if len(items) < APPWRITE_PAGE_SIZE:
                return
            offset += len(items)

    def _load_page(self, offset: int):
        """Read one Appwrite page, tolerating brief Cloud/TLS interruptions."""
        last_error: Exception | None = None
        for attempt in range(APPWRITE_READ_RETRIES):
            try:
                return self._clients.databases.list_documents(
                    database_id=self._config.database_id,
                    collection_id=self._config.chunks_collection_id,
                    queries=[Query.limit(APPWRITE_PAGE_SIZE), Query.offset(offset)],
                )
            except Exception as exc:
                last_error = exc
                if attempt < APPWRITE_READ_RETRIES - 1:
                    time.sleep(0.5 * (2**attempt))
        assert last_error is not None
        raise last_error


def _serialize_vector(vector: list[float]) -> str:
    """Return compact JSON that fits Appwrite string attributes."""
    compact = [round(float(value), 6) for value in vector]
    return json.dumps(compact, separators=(",", ":"))
