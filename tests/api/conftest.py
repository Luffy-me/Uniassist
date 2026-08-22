"""Shared fixtures for API tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from uniassist.ai.models import (
    Citation,
    RefusalAnswer,
    RefusalReason,
    VerificationResult,
    VerifiedAnswer,
)
from uniassist.api.app import create_app
from uniassist.api.dependencies import AppServices, AppSettings
from uniassist.documents.ingestion import DocumentIngestionService
from uniassist.documents.store import JsonDocumentStore
from uniassist.processing.service import DocumentProcessingService
from uniassist.processing.store import ProcessingStore
from uniassist.rag.embeddings import DeterministicEmbeddingProvider
from uniassist.rag.indexing import IndexingService
from uniassist.rag.vector_store import VectorStore

LEAVE_TEXT = (
    "Students may request academic leave by submitting a formal request "
    "to the academic office."
)


class MockAnswerPipeline:
    """Minimal AnswerPipeline stand-in for API tests."""

    def __init__(self, result: VerifiedAnswer | RefusalAnswer) -> None:
        self._result = result
        self.last_question: str | None = None
        self.should_raise: Exception | None = None

    def ask(self, question_text: str) -> VerifiedAnswer | RefusalAnswer:
        if self.should_raise is not None:
            raise self.should_raise
        self.last_question = question_text
        return self._result


def make_verified_answer() -> VerifiedAnswer:
    return VerifiedAnswer(
        answer_text="Students may request academic leave.",
        citations=(
            Citation(
                chunk_id="chunk-1",
                document_id="doc-1",
                title="Academic Leave Regulations",
                page_number=2,
                section="2.1",
                source="TEST",
                source_url="https://example.org/leave",
            ),
        ),
        verification_result=VerificationResult(
            verified=True,
            confidence=1.0,
            supported_claims=("Students may request academic leave.",),
        ),
        model="mock-test",
        generated_at=datetime.now(UTC),
    )


def make_refusal_answer() -> RefusalAnswer:
    return RefusalAnswer(
        reason=RefusalReason.NO_RELEVANT_EVIDENCE,
        message="No relevant evidence was found.",
        verification_result=VerificationResult(
            verified=False,
            confidence=0.0,
            refusal_reason=RefusalReason.NO_RELEVANT_EVIDENCE,
        ),
        model="mock-test",
    )


def build_test_services(
    project_root: Path,
    pipeline: MockAnswerPipeline,
) -> AppServices:
    settings = AppSettings(project_root=project_root, cors_origins=())
    raw_dir = project_root / "data" / "raw"
    metadata_dir = project_root / "data" / "metadata"
    processed_dir = project_root / "data" / "processed"
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
    return AppServices(
        ingestion=DocumentIngestionService(document_store),
        processing=DocumentProcessingService(
            document_store=document_store,
            processing_store=processing_store,
            require_eligibility=False,
        ),
        indexing=IndexingService(
            document_store=document_store,
            processing_store=processing_store,
            vector_store=vector_store,
            embedding_provider=embedding_provider,
            require_eligibility=True,
            metadata_path=rag_dir / "documents.json",
        ),
        pipeline=pipeline,  # type: ignore[arg-type]
        settings=settings,
    )


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "metadata").mkdir(parents=True)
    (tmp_path / "data" / "processed").mkdir(parents=True)
    (tmp_path / "data" / "metadata" / "rag").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def mock_pipeline() -> MockAnswerPipeline:
    return MockAnswerPipeline(make_verified_answer())


@pytest.fixture
def api_client(project_root: Path, mock_pipeline: MockAnswerPipeline) -> TestClient:
    services = build_test_services(project_root, mock_pipeline)
    app = create_app(settings=services.settings, services=services)
    return TestClient(app)


@pytest.fixture
def document_client(
    project_root: Path,
) -> tuple[TestClient, AppServices, MockAnswerPipeline]:
    pipeline = MockAnswerPipeline(make_verified_answer())
    services = build_test_services(project_root, pipeline)
    app = create_app(settings=services.settings, services=services)
    return TestClient(app), services, pipeline
