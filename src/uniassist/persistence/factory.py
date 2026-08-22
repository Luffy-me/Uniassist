"""Construct persistence backends for local or Appwrite storage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from uniassist.persistence.config import (
    AppwriteConfig,
    StorageBackend,
    resolve_data_dir,
    resolve_storage_backend,
)

if TYPE_CHECKING:
    from uniassist.documents.store import DocumentStore


@dataclass(frozen=True)
class PersistenceBundle:
    """All persistence dependencies for UniAssist services."""

    document_store: DocumentStore
    processing_store: Any
    vector_store: Any
    manifest_store: Any | None
    rag_metadata_path: Path | None
    backend: StorageBackend
    appwrite_config: AppwriteConfig | None = None


def build_persistence(project_root: Path | None = None) -> PersistenceBundle:
    root = project_root or Path.cwd()
    backend = resolve_storage_backend()
    if backend == StorageBackend.APPWRITE:
        return _build_appwrite(root)
    return _build_local(root)


def _build_local(root: Path) -> PersistenceBundle:
    from uniassist.documents.store import JsonDocumentStore
    from uniassist.persistence.blob_store import LocalBlobStore
    from uniassist.processing.store import ProcessingStore
    from uniassist.rag.index_metadata import IndexManifestStore
    from uniassist.rag.vector_store import JsonVectorStore

    data_dir = Path(resolve_data_dir(root))
    metadata_dir = data_dir / "metadata"
    rag_dir = metadata_dir / "rag"
    raw_dir = data_dir / "raw"
    return PersistenceBundle(
        document_store=JsonDocumentStore(
            raw_dir=raw_dir,
            index_path=metadata_dir / "documents.json",
            blob_store=LocalBlobStore(raw_dir),
        ),
        processing_store=ProcessingStore(
            processed_dir=data_dir / "processed",
            index_path=metadata_dir / "processing.json",
        ),
        vector_store=JsonVectorStore(rag_dir / "index.json"),
        manifest_store=IndexManifestStore(rag_dir / "index_manifest.json"),
        rag_metadata_path=rag_dir / "documents.json",
        backend=StorageBackend.LOCAL,
    )


def _build_appwrite(root: Path) -> PersistenceBundle:
    from uniassist.persistence.appwrite_blob_store import AppwriteBlobStore
    from uniassist.persistence.appwrite_client import build_appwrite_clients
    from uniassist.persistence.appwrite_document_store import AppwriteDocumentStore
    from uniassist.persistence.appwrite_manifest_store import AppwriteIndexManifestStore
    from uniassist.persistence.appwrite_processing_store import AppwriteProcessingStore
    from uniassist.persistence.appwrite_vector_store import AppwriteVectorStore

    config = AppwriteConfig.from_env()
    config.validate_for_production()
    clients = build_appwrite_clients(config)
    raw_blob_store = AppwriteBlobStore(
        clients=clients,
        bucket_id=config.raw_bucket_id,
        ref_prefix="raw",
    )
    processed_blob_store = AppwriteBlobStore(
        clients=clients,
        bucket_id=config.processed_bucket_id,
        ref_prefix="processed",
    )
    return PersistenceBundle(
        document_store=AppwriteDocumentStore(
            clients=clients,
            blob_store=raw_blob_store,
        ),
        processing_store=AppwriteProcessingStore(
            clients=clients,
            artifact_store=processed_blob_store,
        ),
        vector_store=AppwriteVectorStore(clients),
        manifest_store=AppwriteIndexManifestStore(clients),
        rag_metadata_path=None,
        backend=StorageBackend.APPWRITE,
        appwrite_config=config,
    )
