"""End-to-end RAG integration tests."""

from __future__ import annotations

from tests.rag.conftest import ingest_and_process_text
from uniassist.core.hashing import sha256_hex


def test_full_pipeline_with_tiny_corpus(rag_stack) -> None:
    leave = ingest_and_process_text(
        rag_stack,
        filename="leave.txt",
        content=(
            "Students may request academic leave by submitting a formal request "
            "to the academic office."
        ),
        title="Academic Leave Regulations",
        source="SUSU",
        source_url="https://example.org/leave",
        version="2025-1",
    )
    library = ingest_and_process_text(
        rag_stack,
        filename="library.txt",
        content="University library opening hours are posted on the website.",
        title="Library Hours",
        source="SUSU",
        source_url="https://example.org/library",
        version="2025-1",
    )

    rag_stack["indexing"].index_all_eligible()
    results = rag_stack["retriever"].retrieve(
        "How can a student request academic leave?",
        top_k=2,
    )

    assert len(results) == 2
    assert results[0].chunk.document_id == leave.document_id
    assert results[1].chunk.document_id == library.document_id
    assert results[0].chunk.source_sha256 == leave.sha256
    assert results[0].chunk.document_version == "2025-1"


def test_raw_files_remain_unchanged(rag_stack) -> None:
    content = "Students may request academic leave."
    record = ingest_and_process_text(
        rag_stack,
        filename="leave.txt",
        content=content,
        title="Academic Leave Regulations",
        source="SUSU",
    )
    before = record.local_path.read_bytes()
    rag_stack["indexing"].index_document(record.document_id)
    rag_stack["retriever"].retrieve("academic leave", top_k=1)
    after = record.local_path.read_bytes()
    assert before == after
    assert sha256_hex(before) == record.sha256
