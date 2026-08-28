"""Shared helpers for optional live end-to-end validation tests."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from uniassist.ai.generation import AnswerGenerationService
from uniassist.ai.pipeline import AnswerPipeline
from uniassist.ai.providers.groq import GroqConfigError, GroqProvider
from uniassist.ai.verification import VerificationEngine
from uniassist.documents.ingestion import DocumentIngestionService, IngestRequest
from uniassist.documents.store import JsonDocumentStore
from uniassist.processing.service import DocumentProcessingService
from uniassist.processing.store import ProcessingStore
from uniassist.rag.embedding_factory import create_embedding_provider
from uniassist.rag.indexing import IndexingService
from uniassist.rag.retrieval import Retriever
from uniassist.rag.vector_store import JsonVectorStore

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "e2e"

E2E_DOCUMENTS: tuple[tuple[str, str, str], ...] = (
    ("academic_leave.txt", "Academic Leave Policy", "E2E_ACADEMIC_LEAVE"),
    ("exam_rules.txt", "Examination Regulations", "E2E_EXAM_RULES"),
    ("dormitory.txt", "Dormitory Accommodation Policy", "E2E_DORMITORY"),
    ("tuition.txt", "Tuition and Payment Rules", "E2E_TUITION"),
)

E2E_RETRIEVAL_QUERIES: tuple[tuple[str, str], ...] = (
    ("How can I request academic leave?", "academic_leave.txt"),
    ("What happens if I miss an examination?", "exam_rules.txt"),
    ("How do I apply for a dormitory?", "dormitory.txt"),
    ("When do I need to pay tuition?", "tuition.txt"),
)


@dataclass
class E2EStack:
    """Fully wired test stack backed by Groq when available."""

    root: Path
    document_store: JsonDocumentStore
    processing_store: ProcessingStore
    indexing: IndexingService
    retriever: Retriever
    pipeline: AnswerPipeline
    document_ids: dict[str, str]
    rebuild_report: object


def integration_enabled() -> bool:
    return os.environ.get("UNIASSIST_RUN_GROQ_INTEGRATION") == "1"


def require_groq_runtime() -> None:
    if not integration_enabled():
        pytest.skip("Set UNIASSIST_RUN_GROQ_INTEGRATION=1 to run live E2E tests")
    if not os.environ.get("GROQ_API_KEY", "").strip():
        pytest.skip("GROQ_API_KEY is required for live Groq E2E tests")
    try:
        GroqProvider()._require_client()  # noqa: SLF001
    except GroqConfigError as exc:
        pytest.skip(str(exc))


def build_e2e_stack(tmp_path: Path) -> E2EStack:
    root = tmp_path
    raw_dir = root / "raw"
    metadata_dir = root / "metadata"
    processed_dir = root / "processed"
    rag_dir = metadata_dir / "rag"

    document_store = JsonDocumentStore(
        raw_dir=raw_dir,
        index_path=metadata_dir / "documents.json",
    )
    processing_store = ProcessingStore(
        processed_dir=processed_dir,
        index_path=metadata_dir / "processing.json",
    )
    embedding_provider = create_embedding_provider()
    vector_store = JsonVectorStore(rag_dir / "index.json")
    indexing = IndexingService(
        document_store=document_store,
        processing_store=processing_store,
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        require_eligibility=True,
        metadata_path=rag_dir / "documents.json",
        manifest_path=rag_dir / "index_manifest.json",
    )
    ingestion = DocumentIngestionService(document_store)
    processing = DocumentProcessingService(
        document_store=document_store,
        processing_store=processing_store,
        require_eligibility=False,
    )

    document_ids: dict[str, str] = {}
    for filename, title, source in E2E_DOCUMENTS:
        content = (FIXTURES_DIR / filename).read_text(encoding="utf-8")
        uploaded = ingestion.ingest_bytes(
            filename=filename,
            content=content.encode("utf-8"),
            request=IngestRequest(
                title=title,
                source=source,
                source_url=f"https://example.org/e2e/{filename}",
                version="e2e-1",
            ),
        )
        record = ingestion.activate(uploaded.record.document_id)
        processing.process_document(record.document_id)
        document_ids[filename] = record.document_id

    rebuild_report = indexing.rebuild_index()
    retriever = Retriever(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        indexing_service=indexing,
    )
    provider = GroqProvider()
    pipeline = AnswerPipeline(
        AnswerGenerationService(retriever, provider),
        VerificationEngine(document_store),
        provider,
    )
    return E2EStack(
        root=root,
        document_store=document_store,
        processing_store=processing_store,
        indexing=indexing,
        retriever=retriever,
        pipeline=pipeline,
        document_ids=document_ids,
        rebuild_report=rebuild_report,
    )
