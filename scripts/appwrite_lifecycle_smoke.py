"""Live Appwrite lifecycle smoke test (Phase I)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

os.environ["UNIASSIST_EMBEDDING_PROVIDER"] = "deterministic"

from fastapi.testclient import TestClient

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

LEAVE_TEXT = (
    "Students may request academic leave by submitting a formal request "
    "to the academic office."
)


def _prepare_appwrite_index_state(project_root: Path) -> None:
    from uniassist.persistence.config import StorageBackend, resolve_storage_backend
    from uniassist.rag.embeddings import (
        DEFAULT_DIMENSION,
        DeterministicEmbeddingProvider,
    )
    from uniassist.rag.index_metadata import IndexManifest

    if resolve_storage_backend() != StorageBackend.APPWRITE:
        return

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


def main() -> None:
    if resolve_storage_backend() != StorageBackend.APPWRITE:
        raise SystemExit("SKIP: not appwrite mode")

    project_root = Path.cwd()
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
        indexing, project_root, provider=MockLLMProvider()
    )
    services = build_services(settings, pipeline=pipeline)
    client = TestClient(create_app(settings=settings, services=services))

    title = f"Lifecycle Test {uuid.uuid4().hex[:8]}"
    uploaded = client.post(
        "/documents/upload",
        data={"title": title, "source": "LIFECYCLE_TEST"},
        files={"file": ("lifecycle.txt", LEAVE_TEXT.encode("utf-8"), "text/plain")},
    ).json()
    document_id = uploaded["document"]["document_id"]

    client.post(f"/documents/{document_id}/activate").raise_for_status()
    proc = client.post(f"/documents/{document_id}/process").json()
    if proc["result"]["status"] != "completed":
        raise RuntimeError(f"process failed: {proc}")

    idx = client.post(f"/documents/{document_id}/index")
    if idx.status_code != 200:
        raise RuntimeError(f"index failed: {idx.text}")

    grounded = client.post(
        "/ask", json={"question": "How do I request academic leave?"}
    )
    if grounded.status_code != 200:
        raise RuntimeError(f"ask failed: {grounded.text}")
    body = grounded.json()
    if body.get("status") not in {"answered", "verified"}:
        raise RuntimeError(f"unexpected grounded status: {body}")
    if not body.get("citations"):
        raise RuntimeError(f"missing citations: {body}")

    refusal = client.post("/ask", json={"question": "What is the capital of Mars?"})
    if refusal.status_code != 200:
        raise RuntimeError(f"refusal ask failed: {refusal.text}")
    refusal_body = refusal.json()
    if refusal_body.get("status") not in {"refused", "no_evidence"}:
        raise RuntimeError(f"unexpected refusal status: {refusal_body}")

    _cleanup(document_id, persistence)
    print("LIFECYCLE_PASS")


def _cleanup(document_id: str, persistence) -> None:
    persistence.vector_store.delete_document(document_id)
    from uniassist.persistence.appwrite_blob_store import AppwriteBlobStore
    from uniassist.persistence.appwrite_client import build_appwrite_clients

    config = AppwriteConfig.from_env()
    clients = build_appwrite_clients(config)
    for coll in (config.processing_collection_id, config.documents_collection_id):
        try:
            clients.databases.delete_document(config.database_id, coll, document_id)
        except Exception:
            pass
    record = persistence.document_store.get(document_id)
    if record and record.storage_ref:
        AppwriteBlobStore(
            clients=clients,
            bucket_id=config.raw_bucket_id,
            ref_prefix="raw",
        ).delete(record.storage_ref)


if __name__ == "__main__":
    main()
