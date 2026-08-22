"""Retrieval evaluation regression tests.

These metrics are deterministic regression checks on a small synthetic corpus.
They do not represent real-world retrieval quality on production documents.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.rag.conftest import ingest_and_process_text

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "eval"


@pytest.fixture
def eval_corpus(rag_stack):
    documents = [
        ("academic_leave.txt", "Academic Leave Regulation"),
        ("exam_regulation.txt", "Exam Regulation"),
        ("student_residence.txt", "Student Residence Regulation"),
        ("tuition_regulation.txt", "Tuition Regulation"),
    ]
    records = []
    for filename, title in documents:
        content = (FIXTURES / filename).read_text(encoding="utf-8")
        record = ingest_and_process_text(
            rag_stack,
            filename=filename,
            content=content,
            title=title,
            source="EVAL",
        )
        records.append(record)
    rag_stack["indexing"].index_all_eligible()
    return records


def _recall_at_k(results: list, expected_title: str, k: int) -> float:
    titles = [item.chunk.title for item in results[:k]]
    return 1.0 if expected_title in titles else 0.0


@pytest.mark.parametrize(
    ("query", "expected_title"),
    [
        (item["query"], item["expected_title"])
        for item in json.loads((FIXTURES / "queries.json").read_text(encoding="utf-8"))
    ],
)
def test_eval_recall_metrics(
    eval_corpus,
    rag_stack,
    query: str,
    expected_title: str,
) -> None:
    results = rag_stack["retriever"].retrieve(query, top_k=5)
    assert results, f"no results for query: {query}"
    recall_at_1 = _recall_at_k(results, expected_title, 1)
    recall_at_3 = _recall_at_k(results, expected_title, 3)
    recall_at_5 = _recall_at_k(results, expected_title, 5)
    assert recall_at_3 >= recall_at_1
    assert recall_at_5 >= recall_at_3
    assert recall_at_3 == 1.0, (
        f"Recall@3 failed for {query!r}; got titles: "
        f"{[item.chunk.title for item in results[:3]]}"
    )


def test_min_score_does_not_pad_irrelevant_results(rag_stack, eval_corpus) -> None:
    from uniassist.rag.retrieval import RetrievalConfig, Retriever

    strict = Retriever(
        vector_store=rag_stack["vector_store"],
        embedding_provider=rag_stack["indexing"].embedding_provider,
        indexing_service=rag_stack["indexing"],
        config=RetrievalConfig(top_k=5, min_score=0.99),
    )
    results = strict.retrieve("How can I request academic leave?", top_k=5)
    assert len(results) < 5
