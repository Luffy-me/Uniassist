"""Tests for Appwrite persistence with mocked clients."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from uniassist.documents.models import (
    DocumentRecord,
    DocumentStatus,
    SourceType,
    VerificationState,
)
from uniassist.persistence.appwrite_blob_store import AppwriteBlobStore
from uniassist.persistence.appwrite_client import AppwriteClients
from uniassist.persistence.appwrite_document_store import AppwriteDocumentStore
from uniassist.persistence.appwrite_vector_store import AppwriteVectorStore
from uniassist.persistence.config import AppwriteConfig
from uniassist.rag.models import Chunk


@pytest.fixture
def appwrite_clients() -> AppwriteClients:
    config = AppwriteConfig(
        endpoint="https://cloud.appwrite.io/v1",
        project_id="project",
        api_key="test-key",
        database_id="db",
        documents_collection_id="docs",
        processing_collection_id="proc",
        chunks_collection_id="chunks",
        raw_bucket_id="raw",
        processed_bucket_id="processed",
    )
    databases = MagicMock()
    storage = MagicMock()
    uploaded: set[str] = set()

    def _get_file(bucket_id: str, file_id: str) -> dict:
        if file_id in uploaded:
            return {"$id": file_id}
        raise Exception("missing")

    def _create_file(bucket_id: str, file_id: str, file: object) -> dict:
        uploaded.add(file_id)
        return {"$id": file_id}

    storage.get_file.side_effect = _get_file
    storage.create_file.side_effect = _create_file
    storage.get_file_download.return_value = b"hello"
    databases.list_documents.return_value = {"documents": []}
    databases.get_document.side_effect = Exception("not found")
    return AppwriteClients(databases=databases, storage=storage, config=config)


def test_appwrite_blob_store_deduplicates_by_digest(appwrite_clients) -> None:
    store = AppwriteBlobStore(
        clients=appwrite_clients,
        bucket_id="raw",
        ref_prefix="raw",
    )
    first = store.save(b"hello", "sample.txt")
    second = store.save(b"hello", "sample.txt")
    assert first == second
    appwrite_clients.storage.create_file.assert_called_once()


def test_appwrite_document_store_adds_metadata(appwrite_clients) -> None:
    blob_store = AppwriteBlobStore(
        clients=appwrite_clients,
        bucket_id="raw",
        ref_prefix="raw",
    )
    store = AppwriteDocumentStore(clients=appwrite_clients, blob_store=blob_store)
    record = DocumentRecord(
        document_id="doc-1",
        title="Rules",
        filename="rules.txt",
        content_type="text/plain",
        sha256="abc",
        local_path=Path("virtual://abc"),
        uploaded_at=datetime.now(UTC),
        source="TEST",
        source_type=SourceType.ADMIN_UPLOAD,
        status=DocumentStatus.DRAFT,
        verification_state=VerificationState.PENDING,
        storage_ref="appwrite://raw/raw/file123",
    )
    store.add_record(record)
    appwrite_clients.databases.create_document.assert_called_once()


def test_appwrite_vector_store_persists_chunks(appwrite_clients) -> None:
    appwrite_clients.databases.list_documents.return_value = {"documents": []}
    store = AppwriteVectorStore(appwrite_clients)
    chunk = Chunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        text="Students may request academic leave.",
        chunk_index=0,
        page_number=1,
        section="1",
        source_sha256="abc",
        document_version="v1",
        source="TEST",
        source_url=None,
        title="Rules",
    )
    store.add(chunk, [1.0, 0.0])
    appwrite_clients.databases.create_document.assert_called()


def test_appwrite_vector_store_compacts_large_nvidia_vectors(appwrite_clients) -> None:
    appwrite_clients.databases.list_documents.return_value = {"documents": []}
    store = AppwriteVectorStore(appwrite_clients)
    chunk = Chunk(
        chunk_id="chunk-nvidia",
        document_id="doc-1",
        text="Students may request academic leave.",
        chunk_index=0,
        page_number=1,
        section="1",
        source_sha256="abc",
        document_version="v1",
        source="TEST",
        source_url=None,
        title="Rules",
    )
    vector = [0.123456789 if index % 2 else -0.987654321 for index in range(1024)]

    store.add(chunk, vector)

    payload = appwrite_clients.databases.create_document.call_args.kwargs["data"]
    serialized = payload["embedding"]
    assert len(serialized) < 16384
    assert json.loads(serialized)[0] == -0.987654
