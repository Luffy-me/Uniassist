"""Appwrite Database-backed vector store."""

from __future__ import annotations

import json

from uniassist.persistence.appwrite_client import AppwriteClients
from uniassist.rag.models import Chunk
from uniassist.rag.vector_store import VectorStore


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
                document_id=chunk_id,
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
        for chunk_id in list(self._chunks):
            self.delete(chunk_id)
        super().clear()

    def _persist_chunk(self, chunk: Chunk, vector: list[float]) -> None:
        payload = {
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
            "embedding": json.dumps(vector),
            "chunk_json": json.dumps(chunk.to_dict(), ensure_ascii=False),
        }
        try:
            self._clients.databases.create_document(
                database_id=self._config.database_id,
                collection_id=self._config.chunks_collection_id,
                document_id=chunk.chunk_id,
                data=payload,
            )
        except Exception:
            self._clients.databases.update_document(
                database_id=self._config.database_id,
                collection_id=self._config.chunks_collection_id,
                document_id=chunk.chunk_id,
                data=payload,
            )

    def _load(self) -> None:
        response = self._clients.databases.list_documents(
            database_id=self._config.database_id,
            collection_id=self._config.chunks_collection_id,
        )
        for item in response.get("documents", []):
            chunk_data = json.loads(str(item.get("chunk_json", "{}")))
            if not chunk_data:
                continue
            chunk = Chunk.from_dict(chunk_data)
            vector = json.loads(str(item.get("embedding", "[]")))
            if vector:
                super().add(chunk, vector)
