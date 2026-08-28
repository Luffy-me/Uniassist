"""Ensure API indexing updates the live AnswerPipeline retriever."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import LEAVE_TEXT
from uniassist.ai.pipeline import AnswerPipeline
from uniassist.ai.providers.mock import MockLLMProvider
from uniassist.api.app import create_app
from uniassist.api.dependencies import build_services, load_settings
from uniassist.persistence.config import (
    AppwriteConfig,
    StorageBackend,
    resolve_storage_backend,
)
from uniassist.persistence.factory import build_persistence
from uniassist.rag.indexing import IndexingService


def _ensure_appwrite_schema_if_needed() -> None:
    if resolve_storage_backend() != StorageBackend.APPWRITE:
        return
    from uniassist.persistence.appwrite_client import build_appwrite_clients
    from uniassist.persistence.appwrite_schema import ensure_schema

    config = AppwriteConfig.from_env()
    report = ensure_schema(build_appwrite_clients(config), config)
    if report.failed:
        pytest.fail(
            "Appwrite schema is incomplete for pipeline wiring test: "
            + ", ".join(report.failed)
        )


def _prepare_appwrite_index_state(project_root) -> None:
    if resolve_storage_backend() != StorageBackend.APPWRITE:
        return
    from uniassist.rag.embeddings import (
        DEFAULT_DIMENSION,
        DeterministicEmbeddingProvider,
    )
    from uniassist.rag.index_metadata import IndexManifest

    persistence = build_persistence(project_root)
    if persistence.manifest_store is None:
        return

    vector_store = persistence.vector_store
    vectors = getattr(vector_store, "_vectors", None)
    if not isinstance(vectors, dict):
        return

    expected_dimension = DEFAULT_DIMENSION
    manifest = persistence.manifest_store.load()
    for chunk_id, vector in list(vectors.items()):
        if len(vector) == expected_dimension:
            continue
        if chunk_id.startswith("integration-test-"):
            vector_store.delete(chunk_id)
            continue
        if manifest is None or manifest.dimension == expected_dimension:
            vector_store.delete(chunk_id)

    if len(vector_store) == 0:
        if manifest is not None:
            persistence.manifest_store.clear()
        return

    if manifest is None or manifest.dimension != expected_dimension:
        provider = DeterministicEmbeddingProvider(dimension=expected_dimension)
        persistence.manifest_store.save(
            IndexManifest(
                provider_name=provider.provider_name,
                embedding_model="deterministic-hash-v1",
                dimension=expected_dimension,
            )
        )


def _cleanup_appwrite_document(document_id: str) -> None:
    if resolve_storage_backend() != StorageBackend.APPWRITE:
        return
    from uniassist.persistence.appwrite_client import build_appwrite_clients

    config = AppwriteConfig.from_env()
    clients = build_appwrite_clients(config)
    persistence = build_persistence()
    persistence.vector_store.delete_document(document_id)
    try:
        clients.databases.delete_document(
            database_id=config.database_id,
            collection_id=config.processing_collection_id,
            document_id=document_id,
        )
    except Exception:
        pass
    record = persistence.document_store.get(document_id)
    if record is not None:
        ref = record.storage_ref or str(record.local_path)
        if str(ref).startswith("appwrite://"):
            from uniassist.persistence.appwrite_blob_store import AppwriteBlobStore

            AppwriteBlobStore(
                clients=clients,
                bucket_id=config.raw_bucket_id,
                ref_prefix="raw",
            ).delete(ref)
        try:
            clients.databases.delete_document(
                database_id=config.database_id,
                collection_id=config.documents_collection_id,
                document_id=document_id,
            )
        except Exception:
            pass


def test_indexed_document_is_visible_to_pipeline_retriever(
    project_root,
    monkeypatch,
) -> None:
    monkeypatch.setenv("UNIASSIST_EMBEDDING_PROVIDER", "deterministic")
    _ensure_appwrite_schema_if_needed()
    _prepare_appwrite_index_state(project_root)
    settings = load_settings(project_root)
    persistence = build_persistence(project_root)
    indexing = IndexingService(
        document_store=persistence.document_store,
        processing_store=persistence.processing_store,
        vector_store=persistence.vector_store,
        metadata_path=persistence.rag_metadata_path,
        manifest_store=persistence.manifest_store,
        require_eligibility=True,
    )
    pipeline = AnswerPipeline.from_indexing(
        indexing,
        project_root,
        provider=MockLLMProvider(),
    )
    services = build_services(settings, pipeline=pipeline)
    client = TestClient(create_app(settings=settings, services=services))

    uploaded = client.post(
        "/documents/upload",
        data={
            "title": "Academic Leave Regulations",
            "source": "TEST",
            "source_url": "https://example.org/leave",
        },
        files={"file": ("leave.txt", LEAVE_TEXT.encode("utf-8"), "text/plain")},
    ).json()
    document_id = uploaded["document"]["document_id"]

    try:
        activate_resp = client.post(f"/documents/{document_id}/activate")
        assert activate_resp.status_code == 200, activate_resp.text
        process_resp = client.post(f"/documents/{document_id}/process")
        assert process_resp.status_code == 200, process_resp.text
        assert process_resp.json()["result"]["status"] == "completed"
        index_resp = client.post(f"/documents/{document_id}/index")
        assert index_resp.status_code == 200, index_resp.text

        retriever = services.pipeline._generation._retriever  # noqa: SLF001
        results = retriever.retrieve("academic leave request", top_k=1)
        assert results
        assert results[0].chunk.document_id == document_id
        if resolve_storage_backend() == StorageBackend.APPWRITE:
            assert os.environ.get("UNIASSIST_STORAGE_BACKEND") == "appwrite"
    finally:
        _cleanup_appwrite_document(document_id)
