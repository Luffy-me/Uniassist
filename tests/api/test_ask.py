"""Tests for POST /ask."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.conftest import (
    MockAnswerPipeline,
    build_test_services,
    make_refusal_answer,
)
from uniassist.ai.generation import GenerationError
from uniassist.api.app import create_app
from uniassist.api.schemas import MAX_QUESTION_LENGTH


def test_ask_valid_question(api_client: TestClient) -> None:
    response = api_client.post("/ask", json={"question": "Can I take academic leave?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "verified"
    assert payload["answer"]
    assert payload["citations"]
    assert payload["verification"]["verified"] is True
    assert payload["request_id"]


def test_ask_empty_question_returns_validation_error(api_client: TestClient) -> None:
    response = api_client.post("/ask", json={"question": ""})
    assert response.status_code == 422


def test_ask_whitespace_only_question_returns_bad_request(
    api_client: TestClient,
) -> None:
    response = api_client.post("/ask", json={"question": "   "})
    assert response.status_code == 400
    assert response.json()["error"] == "bad_request"


def test_ask_too_long_question_returns_validation_error(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/ask",
        json={"question": "x" * (MAX_QUESTION_LENGTH + 1)},
    )
    assert response.status_code == 422


def test_ask_refusal_response(project_root, mock_pipeline: MockAnswerPipeline) -> None:
    mock_pipeline._result = make_refusal_answer()
    services = build_test_services(project_root, mock_pipeline)
    client = TestClient(create_app(settings=services.settings, services=services))
    response = client.post("/ask", json={"question": "Moon travel policy?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "refused"
    assert payload["message"]
    assert payload["verification"]["verified"] is False


def test_ask_service_error_maps_to_503(
    project_root,
    mock_pipeline: MockAnswerPipeline,
) -> None:
    mock_pipeline.should_raise = GenerationError("Groq unavailable")
    services = build_test_services(project_root, mock_pipeline)
    client = TestClient(create_app(settings=services.settings, services=services))
    response = client.post("/ask", json={"question": "Can I take academic leave?"})
    assert response.status_code == 503
    assert response.json()["error"] == "service_unavailable"


def test_ask_unexpected_error_maps_to_500(
    project_root,
    mock_pipeline: MockAnswerPipeline,
) -> None:
    mock_pipeline.should_raise = RuntimeError("boom")
    services = build_test_services(project_root, mock_pipeline)
    client = TestClient(
        create_app(settings=services.settings, services=services),
        raise_server_exceptions=False,
    )
    response = client.post("/ask", json={"question": "Can I take academic leave?"})
    assert response.status_code == 500
    assert response.json()["error"] == "internal_error"
    assert "boom" not in response.text


def test_ask_includes_request_id_in_response(api_client: TestClient) -> None:
    response = api_client.post(
        "/ask",
        json={"question": "Can I take academic leave?"},
        headers={"X-Request-ID": "ask-request-12345678"},
    )
    assert response.status_code == 200
    assert response.json()["request_id"] == "ask-request-12345678"
