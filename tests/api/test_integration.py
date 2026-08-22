"""End-to-end API integration tests with mocked AnswerPipeline."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.conftest import (
    MockAnswerPipeline,
    build_test_services,
    make_refusal_answer,
    make_verified_answer,
)
from uniassist.api.app import create_app


def test_api_e2e_verified_answer(project_root) -> None:
    pipeline = MockAnswerPipeline(make_verified_answer())
    services = build_test_services(project_root, pipeline)
    client = TestClient(create_app(settings=services.settings, services=services))

    response = client.post("/ask", json={"question": "Can I apply for academic leave?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "verified"
    assert payload["answer"] == "Students may request academic leave."
    assert payload["citations"][0]["chunk_id"] == "chunk-1"
    assert pipeline.last_question == "Can I apply for academic leave?"


def test_api_e2e_refusal_answer(project_root) -> None:
    pipeline = MockAnswerPipeline(make_refusal_answer())
    services = build_test_services(project_root, pipeline)
    client = TestClient(create_app(settings=services.settings, services=services))

    response = client.post(
        "/ask",
        json={"question": "What is the university policy on moon travel?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "refused"
    assert payload["answer"] is None
    assert payload["message"]
    assert payload["verification"]["refusal_reason"] == "no_relevant_evidence"
