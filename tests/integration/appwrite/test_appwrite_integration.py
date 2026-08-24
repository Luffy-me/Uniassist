"""Live Appwrite Cloud integration tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.integration.appwrite.conftest import require_appwrite_integration
from uniassist.documents.models import (
    DocumentRecord,
    DocumentStatus,
    SourceType,
    VerificationState,
)
from uniassist.persistence.appwrite_blob_store import AppwriteBlobStore
from uniassist.persistence.appwrite_document_store import AppwriteDocumentStore
from uniassist.persistence.appwrite_manifest_store import (
    AppwriteIndexManifestStore,
)
from uniassist.persistence.appwrite_processing_store import AppwriteProcessingStore
from uniassist.persistence.appwrite_vector_store import AppwriteVectorStore
from uniassist.processing.models import ProcessingResult, ProcessingStatus
from uniassist.rag.index_metadata import IndexManifest
from uniassist.rag.models import Chunk

pytestmark = [pytest.mark.integration, pytest.mark.appwrite]


def test_appwrite_configuration_is_present(appwrite_config) -> None:
    require_appwrite_integration()
    summary = appwrite_config.redacted_summary()
    assert summary["endpoint"]
    assert summary["api_key_configured"] == "yes"


def test_documents_table_write_read_delete(
    appwrite_clients,
    appwrite_config,
    test_namespace,
) -> None:
    raw_store = AppwriteBlobStore(
        clients=appwrite_clients,
        bucket_id=appwrite_config.raw_bucket_id,
        ref_prefix="raw",
    )
    store = AppwriteDocumentStore(clients=appwrite_clients, blob_store=raw_store)
    document_id = f"{test_namespace}-doc"
    blob_ref = raw_store.save(b"integration test", f"{document_id}.txt")
    record = DocumentRecord(
        document_id=document_id,
        title="Integration Test",
        filename="integration.txt",
        content_type="text/plain",
        sha256="integration-sha",
        local_path=__import__("pathlib").Path(blob_ref),
        uploaded_at=datetime.now(UTC),
        source="INTEGRATION",
        source_type=SourceType.ADMIN_UPLOAD,
        status=DocumentStatus.DRAFT,
        verification_state=VerificationState.PENDING,
        storage_ref=blob_ref,
    )
    store.add_record(record)
    loaded = store.get(document_id)
    assert loaded is not None
    assert loaded.title == "Integration Test"
    appwrite_clients.databases.delete_document(
        database_id=appwrite_config.database_id,
        collection_id=appwrite_config.documents_collection_id,
        document_id=document_id,
    )
    raw_store.delete(blob_ref)


def test_processing_table_write_read_delete(
    appwrite_clients,
    appwrite_config,
    test_namespace,
) -> None:
    artifact_store = AppwriteBlobStore(
        clients=appwrite_clients,
        bucket_id=appwrite_config.processed_bucket_id,
        ref_prefix="processed",
    )
    store = AppwriteProcessingStore(
        clients=appwrite_clients,
        artifact_store=artifact_store,
    )
    document_id = f"{test_namespace}-proc"
    result = ProcessingResult(
        document_id=document_id,
        status=ProcessingStatus.COMPLETED,
        processor="text",
        input_path=__import__("pathlib").Path("virtual://input"),
        output_path=__import__("pathlib").Path(
            artifact_store.save(
                b'{"document_id":"x","blocks":[]}',
                f"{document_id}.json",
            )
        ),
        processed_at=datetime.now(UTC),
        source_sha256="integration-sha",
        content_hash="hash",
        processor_version="1.0.0",
    )
    store.save_result(result)
    loaded = store.get_result(document_id)
    assert loaded is not None
    assert loaded.status == ProcessingStatus.COMPLETED
    appwrite_clients.databases.delete_document(
        database_id=appwrite_config.database_id,
        collection_id=appwrite_config.processing_collection_id,
        document_id=document_id,
    )
    if result.output_path is not None:
        artifact_store.delete(str(result.output_path))


def test_chunks_table_and_vector_store_round_trip(
    appwrite_clients,
    test_namespace,
) -> None:
    store = AppwriteVectorStore(appwrite_clients)
    chunk_id = f"{test_namespace}-chunk"
    chunk = Chunk(
        chunk_id=chunk_id,
        document_id=f"{test_namespace}-doc",
        text="Students may request academic leave.",
        chunk_index=0,
        page_number=1,
        section="1",
        source_sha256="integration-sha",
        document_version="v1",
        source="INTEGRATION",
        source_url=None,
        title="Integration",
    )
    vector = [1.0, 0.0, 0.5]
    store.add(chunk, vector)
    reloaded = AppwriteVectorStore(appwrite_clients)
    assert chunk_id in reloaded._chunks  # noqa: SLF001
    assert reloaded._vectors[chunk_id] == vector  # noqa: SLF001
    store.delete(chunk_id)


def test_index_manifest_persistence(appwrite_clients, test_namespace) -> None:
    store = AppwriteIndexManifestStore(appwrite_clients)
    manifest = IndexManifest(
        provider_name="deterministic",
        embedding_model="deterministic-hash-v1",
        dimension=768,
    )
    store.save(manifest)
    loaded = store.load()
    assert loaded is not None
    assert loaded.embedding_model == manifest.embedding_model
    store.clear()


def test_raw_and_processed_bucket_round_trip(
    appwrite_clients,
    appwrite_config,
    test_namespace,
) -> None:
    for bucket_id, prefix in (
        (appwrite_config.raw_bucket_id, "raw"),
        (appwrite_config.processed_bucket_id, "processed"),
    ):
        store = AppwriteBlobStore(
            clients=appwrite_clients,
            bucket_id=bucket_id,
            ref_prefix=prefix,
        )
        first = store.save(b"bucket integration", f"{test_namespace}-{prefix}.txt")
        assert store.exists(first)
        assert store.read(first) == b"bucket integration"
        duplicate = store.save(b"bucket integration", f"{test_namespace}-{prefix}.txt")
        assert duplicate == first
        store.delete(first)
        assert not store.exists(first)


def test_duplicate_document_metadata_is_rejected(
    appwrite_clients,
    appwrite_config,
    test_namespace,
) -> None:
    raw_store = AppwriteBlobStore(
        clients=appwrite_clients,
        bucket_id=appwrite_config.raw_bucket_id,
        ref_prefix="raw",
    )
    store = AppwriteDocumentStore(clients=appwrite_clients, blob_store=raw_store)
    document_id = f"{test_namespace}-dup"
    blob_ref = raw_store.save(b"duplicate", f"{document_id}.txt")
    record = DocumentRecord(
        document_id=document_id,
        title="Duplicate Test",
        filename="duplicate.txt",
        content_type="text/plain",
        sha256="duplicate-sha",
        local_path=__import__("pathlib").Path(blob_ref),
        uploaded_at=datetime.now(UTC),
        source="INTEGRATION",
        source_type=SourceType.ADMIN_UPLOAD,
        status=DocumentStatus.DRAFT,
        verification_state=VerificationState.PENDING,
        storage_ref=blob_ref,
    )
    store.add_record(record)
    with pytest.raises(ValueError, match="already exists"):
        store.add_record(record)
    appwrite_clients.databases.delete_document(
        database_id=appwrite_config.database_id,
        collection_id=appwrite_config.documents_collection_id,
        document_id=document_id,
    )
    raw_store.delete(blob_ref)
