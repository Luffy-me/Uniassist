"""Migrate local UniAssist data into Appwrite Cloud."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from uniassist.documents.models import DocumentRecord
from uniassist.documents.store import JsonDocumentStore
from uniassist.persistence.appwrite_blob_store import AppwriteBlobStore
from uniassist.persistence.appwrite_client import build_appwrite_clients
from uniassist.persistence.appwrite_document_store import AppwriteDocumentStore
from uniassist.persistence.appwrite_manifest_store import AppwriteIndexManifestStore
from uniassist.persistence.appwrite_processing_store import AppwriteProcessingStore
from uniassist.persistence.appwrite_vector_store import AppwriteVectorStore
from uniassist.persistence.config import AppwriteConfig, resolve_data_dir
from uniassist.processing.store import ProcessingStore
from uniassist.rag.index_metadata import IndexManifestStore
from uniassist.rag.vector_store import JsonVectorStore


@dataclass
class MigrationReport:
    documents_migrated: int = 0
    documents_skipped: int = 0
    processing_migrated: int = 0
    chunks_migrated: int = 0
    dry_run: bool = True


def migrate(*, project_root: Path, dry_run: bool) -> MigrationReport:
    config = AppwriteConfig.from_env()
    config.validate_for_production()
    clients = build_appwrite_clients(config)
    data_dir = Path(resolve_data_dir(project_root))
    local_documents = JsonDocumentStore(
        raw_dir=data_dir / "raw",
        index_path=data_dir / "metadata" / "documents.json",
    )
    local_processing = ProcessingStore(
        processed_dir=data_dir / "processed",
        index_path=data_dir / "metadata" / "processing.json",
    )
    local_vectors = JsonVectorStore(data_dir / "metadata" / "rag" / "index.json")
    local_manifest = IndexManifestStore(
        data_dir / "metadata" / "rag" / "index_manifest.json"
    )

    if dry_run:
        return MigrationReport(
            documents_migrated=len(local_documents.list_records()),
            processing_migrated=len(local_processing.list_results()),
            chunks_migrated=len(local_vectors),
            dry_run=True,
        )

    raw_store = AppwriteBlobStore(
        clients,
        bucket_id=config.raw_bucket_id,
        ref_prefix="raw",
    )
    processed_store = AppwriteBlobStore(
        clients,
        bucket_id=config.processed_bucket_id,
        ref_prefix="processed",
    )
    target_documents = AppwriteDocumentStore(clients, blob_store=raw_store)
    target_processing = AppwriteProcessingStore(
        clients,
        artifact_store=processed_store,
    )
    target_vectors = AppwriteVectorStore(clients)
    target_manifest = AppwriteIndexManifestStore(clients)

    report = MigrationReport(dry_run=False)
    for record in local_documents.list_records():
        if target_documents.find_by_sha256(record.sha256) is not None:
            report.documents_skipped += 1
            continue
        content = local_documents.read_blob(record)
        blob_ref = raw_store.save(content, record.filename, digest=record.sha256)
        migrated = DocumentRecord(
            document_id=record.document_id,
            title=record.title,
            filename=record.filename,
            content_type=record.content_type,
            sha256=record.sha256,
            local_path=Path(blob_ref),
            uploaded_at=record.uploaded_at,
            source=record.source,
            source_type=record.source_type,
            source_url=record.source_url,
            effective_date=record.effective_date,
            version=record.version,
            status=record.status,
            verification_state=record.verification_state,
            notes=record.notes,
            storage_ref=blob_ref,
        )
        target_documents.add_record(migrated)
        report.documents_migrated += 1

    for result in local_processing.list_results():
        target_processing.save_result(result)
        if result.output_path and result.output_path.exists():
            payload = result.output_path.read_bytes()
            processed_store.save(
                payload,
                result.output_path.name,
            )
        report.processing_migrated += 1

    for chunk in local_vectors.list_chunks():
        vector = local_vectors._vectors[chunk.chunk_id]  # noqa: SLF001
        target_vectors.add(chunk, vector)
        report.chunks_migrated += 1

    manifest = local_manifest.load()
    if manifest is not None:
        target_manifest.save(manifest)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate local UniAssist data to Appwrite"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    report = migrate(project_root=Path(args.project_root), dry_run=args.dry_run)
    print(json.dumps(report.__dict__, indent=2))


if __name__ == "__main__":
    main()
