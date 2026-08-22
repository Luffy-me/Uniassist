"""Tests for health and status endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import MockAnswerPipeline, build_test_services
from uniassist.api.app import create_app
from uniassist.api.dependencies import AppServices, AppSettings


def test_health_returns_ok(api_client: TestClient) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_returns_safe_system_information(api_client: TestClient) -> None:
    response = api_client.get("/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["application_version"]
    assert "request_id" in payload
    assert "nvidia_configured" in payload
    assert "nvidia_reachable" in payload
    assert "nvidia_health_message" in payload
    assert "NVIDIA_API_KEY" not in response.text
    assert "rag_available" in payload


def test_status_reflects_nvidia_configuration(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key-not-logged")
    monkeypatch.setenv("NVIDIA_CHAT_MODEL", "meta/llama-3.1-8b-instruct")
    response = api_client.get("/status")
    assert response.json()["nvidia_configured"] is True
    assert "test-key-not-logged" not in response.text


def test_request_id_is_generated(api_client: TestClient) -> None:
    response = api_client.get("/status")
    assert response.headers.get("X-Request-ID")
    assert response.json()["request_id"] == response.headers.get("X-Request-ID")


def test_request_id_is_propagated(api_client: TestClient) -> None:
    custom_id = "client-request-12345678"
    response = api_client.get("/status", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_id
    assert response.json()["request_id"] == custom_id


def test_cors_is_not_enabled_by_default(
    project_root,
    mock_pipeline: MockAnswerPipeline,
) -> None:
    services = build_test_services(project_root, mock_pipeline)
    app = create_app(settings=services.settings, services=services)
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_cors_can_be_configured(
    project_root,
    mock_pipeline: MockAnswerPipeline,
) -> None:
    settings = AppSettings(
        project_root=project_root,
        cors_origins=("http://localhost:3000",),
    )
    services = build_test_services(project_root, mock_pipeline)
    services = AppServices(
        ingestion=services.ingestion,
        processing=services.processing,
        indexing=services.indexing,
        pipeline=mock_pipeline,  # type: ignore[arg-type]
        settings=settings,
    )
    app = create_app(settings=settings, services=services)
    client = TestClient(app)
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
