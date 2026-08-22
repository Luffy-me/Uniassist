"""Ensure API indexing updates the live AnswerPipeline retriever."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.conftest import LEAVE_TEXT
from uniassist.ai.pipeline import AnswerPipeline
from uniassist.ai.providers.mock import MockLLMProvider
from uniassist.api.app import create_app
from uniassist.api.dependencies import build_services, load_settings
from uniassist.persistence.factory import build_persistence
from uniassist.rag.indexing import IndexingService


def test_indexed_document_is_visible_to_pipeline_retriever(
    project_root,
    monkeypatch,
) -> None:
    monkeypatch.setenv("UNIASSIST_EMBEDDING_PROVIDER", "deterministic")
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
        data={"title": "Academic Leave Regulations", "source": "TEST"},
        files={"file": ("leave.txt", LEAVE_TEXT.encode("utf-8"), "text/plain")},
    ).json()
    document_id = uploaded["document"]["document_id"]

    client.post(f"/documents/{document_id}/activate")
    client.post(f"/documents/{document_id}/process")
    client.post(f"/documents/{document_id}/index")

    retriever = services.pipeline._generation._retriever  # noqa: SLF001
    results = retriever.retrieve("academic leave request", top_k=1)
    assert results
    assert results[0].chunk.document_id == document_id
