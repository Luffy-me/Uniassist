"""Optional live NVIDIA end-to-end validation (Phases C–O)."""

from __future__ import annotations

import time

import pytest

from tests.e2e.helpers import (
    E2E_RETRIEVAL_QUERIES,
    build_e2e_stack,
    require_nvidia_runtime,
)
from uniassist.ai.models import RefusalAnswer, VerifiedAnswer
from uniassist.ai.providers.nvidia_client import NVIDIAClient, NVIDIAClientConfig
from uniassist.ai.providers.nvidia_config import (
    check_nvidia_health,
    resolve_api_key,
    resolve_base_url,
)
from uniassist.rag.embedding_factory import create_embedding_provider

pytestmark = [pytest.mark.integration, pytest.mark.nvidia]


@pytest.fixture(scope="module")
def nvidia_health():
    require_nvidia_runtime()
    base_url = resolve_base_url()
    api_key = resolve_api_key(base_url)
    return check_nvidia_health(base_url=base_url, api_key=api_key)


@pytest.fixture(scope="module")
def nvidia_client(nvidia_health):
    return NVIDIAClient(NVIDIAClientConfig.from_env())


@pytest.fixture(scope="module")
def e2e_stack(tmp_path_factory):
    require_nvidia_runtime()
    return build_e2e_stack(tmp_path_factory.mktemp("e2e-nvidia"))


def test_nvidia_nim_is_reachable(nvidia_health) -> None:
    assert nvidia_health.reachable is True
    assert nvidia_health.chat_model
    assert nvidia_health.embedding_model or nvidia_health.available_models


def test_nvidia_models_include_configured_chat_model(nvidia_client) -> None:
    models = nvidia_client.list_models()
    assert models
    assert nvidia_client.model in models


def test_real_nvidia_embedding_generation() -> None:
    require_nvidia_runtime()
    provider = create_embedding_provider(prefer_nvidia=True)
    text = "Students may apply for academic leave."
    vector = provider.embed_text(text)
    assert vector
    assert all(isinstance(value, float) for value in vector)
    assert provider.dimension > 0
    assert provider.dimension == len(vector)
    second = provider.embed_text(text)
    assert len(second) == provider.dimension


def test_real_nvidia_chat_generation(nvidia_client) -> None:
    response = nvidia_client.chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "You are a test assistant. Answer only from the supplied evidence."
                ),
            },
            {
                "role": "user",
                "content": (
                    "What is the rule?\n\nEvidence:\n"
                    "The student must submit the application before the deadline."
                ),
            },
        ]
    )
    content = response["choices"][0]["message"]["content"]
    assert content
    assert "NVIDIA_API_KEY" not in content


def test_real_nvidia_index_manifest(e2e_stack) -> None:
    report = e2e_stack.rebuild_report
    stats = e2e_stack.indexing.stats()
    assert report.chunks_created > 0
    assert report.embeddings_generated > 0
    assert report.provider_name == "nvidia"
    assert report.embedding_dimension > 0
    assert stats.provider_name == "nvidia"
    assert stats.embedding_model
    assert stats.embedding_dimension == report.embedding_dimension


@pytest.mark.parametrize(
    ("query", "expected_fixture"),
    E2E_RETRIEVAL_QUERIES,
)
def test_real_retrieval_returns_expected_document(
    e2e_stack,
    query: str,
    expected_fixture: str,
) -> None:
    results = e2e_stack.retriever.retrieve(query, top_k=3)
    assert results, f"No retrieval results for: {query}"
    top = results[0]
    expected_id = e2e_stack.document_ids[expected_fixture]
    retrieved_ids = {item.chunk.document_id for item in results}
    assert expected_id in retrieved_ids
    assert top.similarity_score > 0
    assert top.chunk.chunk_id


def test_real_pipeline_grounded_answers(e2e_stack) -> None:
    leave = e2e_stack.pipeline.ask("How can I request academic leave?")
    assert isinstance(leave, VerifiedAnswer)
    assert leave.citations
    leave_doc_id = e2e_stack.document_ids["academic_leave.txt"]
    assert leave.citations[0].document_id == leave_doc_id

    dorm = e2e_stack.pipeline.ask("How do I apply for a dormitory?")
    assert isinstance(dorm, VerifiedAnswer)
    assert dorm.citations
    dorm_doc_id = e2e_stack.document_ids["dormitory.txt"]
    assert dorm.citations[0].document_id == dorm_doc_id


def test_real_pipeline_refuses_out_of_domain(e2e_stack) -> None:
    refusal = e2e_stack.pipeline.ask(
        "What is the university policy for traveling to Mars?"
    )
    assert isinstance(refusal, RefusalAnswer)


def test_citations_reference_real_indexed_chunks(e2e_stack) -> None:
    answer = e2e_stack.pipeline.ask("How can I request academic leave?")
    assert isinstance(answer, VerifiedAnswer)
    for citation in answer.citations:
        assert citation.chunk_id
        assert citation.document_id in e2e_stack.document_ids.values()
        assert citation.title
        assert citation.source.startswith("E2E_")


def test_performance_measurements(e2e_stack) -> None:
    questions = [
        "How can I request academic leave?",
        "What happens if I miss an examination?",
        "How do I apply for a dormitory?",
        "When do I need to pay tuition?",
        "What is the university policy for traveling to Mars?",
    ]
    totals: list[float] = []
    for question in questions:
        started = time.perf_counter()
        e2e_stack.pipeline.ask(question)
        totals.append((time.perf_counter() - started) * 1000)
    assert len(totals) == 5
    assert min(totals) >= 0
    assert max(totals) >= min(totals)
    average = sum(totals) / len(totals)
    assert average >= 0
