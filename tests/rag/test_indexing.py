"""Tests for indexing service."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.rag.conftest import ingest_and_process_text, make_normalized
from uniassist.documents.ingestion import IngestRequest
from uniassist.documents.models import DocumentRecord, DocumentStatus, VerificationState
from uniassist.processing.models import ProcessingResult, ProcessingStatus
from uniassist.rag.indexing import IndexingEligibilityError


def test_index_processed_document(rag_stack) -> None:
    record = ingest_and_process_text(
        rag_stack,
        filename="leave.txt",
        content="Students may request academic leave by submitting a form.",
        title="Academic Leave Regulations",
        source="SUSU",
    )
    result = rag_stack["indexing"].index_document(record.document_id)
    assert result.chunks_indexed >= 1
    assert len(rag_stack["vector_store"]) == result.chunks_indexed


def test_metadata_and_provenance_are_preserved(rag_stack) -> None:
    record = ingest_and_process_text(
        rag_stack,
        filename="leave.txt",
        content="Students may request academic leave.",
        title="Academic Leave Regulations",
        source="SUSU",
        source_url="https://example.org/leave",
        version="2025-1",
    )
    rag_stack["indexing"].index_document(record.document_id)
    chunk = rag_stack["vector_store"].list_chunks()[0]
    assert chunk.document_id == record.document_id
    assert chunk.source == "SUSU"
    assert chunk.source_url == "https://example.org/leave"
    assert chunk.document_version == "2025-1"
    assert chunk.source_sha256 == record.sha256


def test_draft_document_is_excluded(rag_stack) -> None:
    ingestion = rag_stack["ingestion"]
    processing = rag_stack["processing"]
    uploaded = ingestion.ingest_bytes(
        filename="draft.txt",
        content=b"Draft content only.",
        request=IngestRequest(title="Draft", source="SUSU"),
    )
    processing.process_document(uploaded.record.document_id)
    with pytest.raises(IndexingEligibilityError, match="ACTIVE"):
        rag_stack["indexing"].index_document(uploaded.record.document_id)


def test_reindexing_replaces_old_chunks(rag_stack) -> None:
    record = ingest_and_process_text(
        rag_stack,
        filename="leave.txt",
        content="Students may request academic leave.",
        title="Academic Leave Regulations",
        source="SUSU",
        version="v1",
    )
    rag_stack["indexing"].index_document(record.document_id)
    first_count = len(rag_stack["vector_store"])

    processing_store = rag_stack["processing_store"]
    normalized = make_normalized(
        document_id=record.document_id,
        title="Academic Leave Regulations",
        source="SUSU",
        source_url=None,
        source_sha256=record.sha256,
        blocks=[("Updated leave policy text for version two.", 1, "1.0")],
    )
    processing_store.save_normalized(normalized)
    processing_store.save_result(
        ProcessingResult(
            document_id=record.document_id,
            status=ProcessingStatus.COMPLETED,
            processor="text",
            input_path=record.local_path,
            output_path=processing_store.output_dir_for(
                record.document_id,
                record.sha256,
            )
            / "normalized.json",
            processed_at=datetime.now(UTC),
            source_sha256=record.sha256,
        )
    )

    document_store = rag_stack["document_store"]
    updated = DocumentRecord(
        document_id=record.document_id,
        title=record.title,
        filename=record.filename,
        content_type=record.content_type,
        sha256=record.sha256,
        local_path=record.local_path,
        uploaded_at=record.uploaded_at,
        source=record.source,
        source_type=record.source_type,
        source_url=record.source_url,
        effective_date=record.effective_date,
        version="v2",
        status=DocumentStatus.ACTIVE,
        verification_state=VerificationState.VERIFIED,
        notes=record.notes,
    )
    document_store.update_record(updated)
    rag_stack["indexing"].index_document(record.document_id)
    assert len(rag_stack["vector_store"]) == first_count
    assert rag_stack["vector_store"].list_chunks()[0].document_version == "v2"


def test_pending_document_is_excluded(rag_stack) -> None:
    ingestion = rag_stack["ingestion"]
    processing = rag_stack["processing"]
    uploaded = ingestion.ingest_bytes(
        filename="pending.txt",
        content=b"Pending content.",
        request=IngestRequest(title="Pending", source="SUSU"),
    )
    record = uploaded.record
    processing.process_document(record.document_id)
    active = DocumentRecord(
        document_id=record.document_id,
        title=record.title,
        filename=record.filename,
        content_type=record.content_type,
        sha256=record.sha256,
        local_path=record.local_path,
        uploaded_at=record.uploaded_at,
        source=record.source,
        source_type=record.source_type,
        source_url=record.source_url,
        effective_date=record.effective_date,
        version=record.version,
        status=DocumentStatus.ACTIVE,
        verification_state=VerificationState.PENDING,
        notes=record.notes,
    )
    rag_stack["document_store"].update_record(active)
    with pytest.raises(IndexingEligibilityError, match="VERIFIED"):
        rag_stack["indexing"].index_document(record.document_id)
