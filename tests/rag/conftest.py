"""Shared fixtures for RAG tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from uniassist.documents.ingestion import DocumentIngestionService, IngestRequest
from uniassist.documents.store import JsonDocumentStore
from uniassist.processing.models import NormalizedBlock, NormalizedDocument
from uniassist.processing.service import DocumentProcessingService
from uniassist.processing.store import ProcessingStore
from uniassist.rag.embeddings import DeterministicEmbeddingProvider
from uniassist.rag.indexing import IndexingService
from uniassist.rag.models import ChunkConfig
from uniassist.rag.retrieval import Retriever
from uniassist.rag.vector_store import VectorStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def rag_stack(tmp_path: Path):
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
        chunk_config=ChunkConfig(max_chars=200, overlap=20),
        require_eligibility=True,
        metadata_path=rag_dir / "documents.json",
    )
    retriever = Retriever(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        indexing_service=indexing,
        require_eligibility=True,
    )
    return {
        "ingestion": ingestion,
        "processing": processing,
        "indexing": indexing,
        "retriever": retriever,
        "document_store": document_store,
        "processing_store": processing_store,
        "vector_store": vector_store,
    }


def make_normalized(
    *,
    document_id: str,
    title: str,
    source: str,
    source_url: str | None,
    source_sha256: str,
    blocks: list[tuple[str, int | None, str | None]],
) -> NormalizedDocument:
    return NormalizedDocument(
        document_id=document_id,
        title=title,
        source=source,
        source_url=source_url,
        source_sha256=source_sha256,
        processor="text",
        processor_version="1.0.0",
        processed_at=datetime.now(UTC),
        blocks=[
            NormalizedBlock(text=text, page_number=page, section=section)
            for text, page, section in blocks
        ],
    )


def ingest_and_process_text(
    stack: dict,
    *,
    filename: str,
    content: str,
    title: str,
    source: str,
    source_url: str | None = None,
    version: str | None = None,
    activate: bool = True,
):
    ingestion: DocumentIngestionService = stack["ingestion"]
    processing: DocumentProcessingService = stack["processing"]
    request = IngestRequest(
        title=title,
        source=source,
        source_url=source_url,
        version=version,
    )
    uploaded = ingestion.ingest_bytes(
        filename=filename,
        content=content.encode("utf-8"),
        request=request,
    )
    record = uploaded.record
    if activate:
        record = ingestion.activate(record.document_id)
    processing.process_document(record.document_id)
    return record
