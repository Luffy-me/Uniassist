"""Tests for retrieval."""

from __future__ import annotations

import pytest

from tests.rag.conftest import ingest_and_process_text
from uniassist.documents.models import DocumentRecord, DocumentStatus, VerificationState
from uniassist.rag.retrieval import RetrievalError


def test_relevant_chunk_ranks_higher(rag_stack) -> None:
    leave = ingest_and_process_text(
        rag_stack,
        filename="leave.txt",
        content=(
            "Students may request academic leave by submitting a formal request "
            "to the academic office."
        ),
        title="Academic Leave Regulations",
        source="SUSU",
    )
    ingest_and_process_text(
        rag_stack,
        filename="library.txt",
        content="University library opening hours are posted on the website.",
        title="Library Hours",
        source="SUSU",
    )
    rag_stack["indexing"].index_document(leave.document_id)
    rag_stack["indexing"].index_all_eligible()

    results = rag_stack["retriever"].retrieve(
        "How can a student request academic leave?",
        top_k=2,
    )
    assert results
    assert results[0].chunk.title == "Academic Leave Regulations"
    assert results[0].similarity_score >= results[1].similarity_score


def test_provenance_fields_are_present(rag_stack) -> None:
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
    result = rag_stack["retriever"].retrieve("academic leave", top_k=1)[0]
    chunk = result.chunk
    assert chunk.document_id == record.document_id
    assert chunk.chunk_id
    assert chunk.source_sha256 == record.sha256
    assert chunk.document_version == "2025-1"
    assert chunk.source == "SUSU"
    assert chunk.source_url == "https://example.org/leave"
    assert result.similarity_score is not None
    assert result.rank == 1


def test_empty_query_is_rejected(rag_stack) -> None:
    with pytest.raises(RetrievalError, match="empty"):
        rag_stack["retriever"].retrieve("   ", top_k=3)


def test_invalid_top_k_is_rejected(rag_stack) -> None:
    with pytest.raises(RetrievalError, match="top_k"):
        rag_stack["retriever"].retrieve("academic leave", top_k=0)


def test_contact_questions_prefer_email_chunks(rag_stack) -> None:
    nav = ingest_and_process_text(
        rag_stack,
        filename="nav.txt",
        content="International Relations International Office Useful Information",
        title="International Relations at a Glance",
        source="SUSU",
    )
    support = ingest_and_process_text(
        rag_stack,
        filename="support.txt",
        content=(
            "International Student Support. Email: applicant@susu.ru "
            "(mailto:applicant@susu.ru). Address: Lenin Ave., 76."
        ),
        title="International Student Support",
        source="SUSU",
        source_url=(
            "https://www.susu.ru/en/international-relations-0/"
            "international-office/international-student-support"
        ),
    )
    rag_stack["indexing"].index_document(nav.document_id)
    rag_stack["indexing"].index_document(support.document_id)

    email_hits = rag_stack["retriever"].retrieve("International email address", top_k=3)
    assert email_hits
    assert "applicant@susu.ru" in email_hits[0].chunk.text

    help_hits = rag_stack["retriever"].retrieve(
        "Where can international student get help at susu?",
        top_k=3,
    )
    assert help_hits
    assert help_hits[0].chunk.title == "International Student Support"


def test_draft_document_not_retrieved_after_lifecycle_change(rag_stack) -> None:
    ingestion = rag_stack["ingestion"]
    record = ingest_and_process_text(
        rag_stack,
        filename="leave.txt",
        content="Students may request academic leave.",
        title="Academic Leave Regulations",
        source="SUSU",
    )
    rag_stack["indexing"].index_document(record.document_id)
    assert rag_stack["retriever"].retrieve("academic leave", top_k=1)

    draft = ingestion.get_document(record.document_id)
    assert draft is not None
    archived = DocumentRecord(
        document_id=draft.document_id,
        title=draft.title,
        filename=draft.filename,
        content_type=draft.content_type,
        sha256=draft.sha256,
        local_path=draft.local_path,
        uploaded_at=draft.uploaded_at,
        source=draft.source,
        source_type=draft.source_type,
        source_url=draft.source_url,
        effective_date=draft.effective_date,
        version=draft.version,
        status=DocumentStatus.DRAFT,
        verification_state=VerificationState.PENDING,
        notes=draft.notes,
    )
    rag_stack["document_store"].update_record(archived)
    assert rag_stack["retriever"].retrieve("academic leave", top_k=1) == []
