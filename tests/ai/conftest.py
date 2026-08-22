"""Shared fixtures for AI tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from uniassist.ai.claim_verification import DeterministicSemanticVerifier
from uniassist.ai.generation import AnswerGenerationService
from uniassist.ai.models import EvidenceItem
from uniassist.ai.pipeline import AnswerPipeline
from uniassist.ai.providers.mock import MockLLMProvider
from uniassist.ai.verification import VerificationEngine
from uniassist.documents.ingestion import DocumentIngestionService, IngestRequest
from uniassist.documents.models import (
    DocumentRecord,
    DocumentStatus,
    SourceType,
    VerificationState,
)
from uniassist.documents.store import JsonDocumentStore
from uniassist.processing.service import DocumentProcessingService
from uniassist.processing.store import ProcessingStore
from uniassist.rag.embeddings import DeterministicEmbeddingProvider
from uniassist.rag.indexing import IndexingService
from uniassist.rag.models import Chunk
from uniassist.rag.retrieval import Retriever
from uniassist.rag.vector_store import VectorStore

LEAVE_TEXT = (
    "Students may request academic leave by submitting a formal request "
    "to the academic office."
)
LIBRARY_TEXT = "University library opening hours are posted on the website."


@pytest.fixture
def ai_stack(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    metadata_dir = tmp_path / "metadata"
    processed_dir = tmp_path / "processed"
    rag_dir = metadata_dir / "rag"

    document_store = JsonDocumentStore(
        raw_dir=raw_dir,
        index_path=metadata_dir / "documents.json",
    )
    processing_store = ProcessingStore(
        processed_dir=processed_dir,
        index_path=metadata_dir / "processing.json",
    )
    vector_store = VectorStore()
    embedding_provider = DeterministicEmbeddingProvider()
    ingestion = DocumentIngestionService(document_store)
    processing = DocumentProcessingService(
        document_store=document_store,
        processing_store=processing_store,
        require_eligibility=False,
    )
    indexing = IndexingService(
        document_store=document_store,
        processing_store=processing_store,
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        require_eligibility=True,
        metadata_path=rag_dir / "documents.json",
    )
    retriever = Retriever(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        indexing_service=indexing,
        require_eligibility=True,
    )
    provider = MockLLMProvider()
    generation = AnswerGenerationService(retriever, provider)
    verification = VerificationEngine(
        document_store,
        semantic_verifier=DeterministicSemanticVerifier(),
    )
    pipeline = AnswerPipeline(generation, verification, provider)
    return {
        "ingestion": ingestion,
        "processing": processing,
        "indexing": indexing,
        "retriever": retriever,
        "provider": provider,
        "generation": generation,
        "verification": verification,
        "pipeline": pipeline,
        "document_store": document_store,
        "vector_store": vector_store,
    }


def ingest_process_index(
    stack: dict,
    *,
    filename: str,
    content: str,
    title: str,
    activate: bool = True,
    version: str | None = None,
) -> DocumentRecord:
    uploaded = stack["ingestion"].ingest_bytes(
        filename=filename,
        content=content.encode("utf-8"),
        request=IngestRequest(
            title=title,
            source="SUSU",
            source_url=f"https://example.org/{filename}",
            version=version,
        ),
    )
    record = uploaded.record
    if activate:
        record = stack["ingestion"].activate(record.document_id)
    stack["processing"].process_document(record.document_id)
    if activate:
        stack["indexing"].index_document(record.document_id)
    return record


def make_evidence(
    *,
    chunk_id: str,
    document_id: str,
    title: str,
    text: str,
    version: str | None = "2025-1",
) -> EvidenceItem:
    return EvidenceItem(
        chunk_id=chunk_id,
        document_id=document_id,
        title=title,
        text=text,
        page_number=4,
        section="2.1",
        source="SUSU",
        source_url="https://example.org/doc",
        document_version=version,
        source_sha256=f"sha-{document_id}",
        effective_date="2025-09-01",
        similarity_score=0.9,
    )


def make_chunk(**kwargs) -> Chunk:
    defaults = {
        "chunk_id": "chunk-1",
        "document_id": "doc-1",
        "text": LEAVE_TEXT,
        "chunk_index": 0,
        "page_number": 4,
        "section": "2.1",
        "source_sha256": "sha",
        "document_version": "2025-1",
        "source": "SUSU",
        "source_url": "https://example.org/doc",
        "title": "Academic Leave Regulations",
    }
    defaults.update(kwargs)
    return Chunk(**defaults)


def make_active_record(
    document_store: JsonDocumentStore,
    *,
    document_id: str,
    title: str,
    version: str | None = "2025-1",
    status: DocumentStatus = DocumentStatus.ACTIVE,
    verification_state: VerificationState = VerificationState.VERIFIED,
) -> DocumentRecord:
    record = DocumentRecord(
        document_id=document_id,
        title=title,
        filename="rules.txt",
        content_type="text/plain",
        sha256=f"sha-{document_id}",
        local_path=Path(f"/tmp/{document_id}.txt"),
        uploaded_at=datetime.now(UTC),
        source="SUSU",
        source_type=SourceType.ADMIN_UPLOAD,
        status=status,
        verification_state=verification_state,
        version=version,
    )
    document_store.add_record(record)
    return record
