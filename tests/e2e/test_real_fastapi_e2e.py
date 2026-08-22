"""Optional live FastAPI end-to-end validation (Phase K)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.e2e.helpers import build_e2e_stack, require_nvidia_runtime
from uniassist.api.app import create_app
from uniassist.api.dependencies import AppServices, AppSettings
from uniassist.documents.ingestion import DocumentIngestionService
from uniassist.processing.service import DocumentProcessingService

pytestmark = [pytest.mark.integration, pytest.mark.nvidia]


@pytest.fixture(scope="module")
def real_api_client(tmp_path_factory):
    require_nvidia_runtime()
    stack = build_e2e_stack(tmp_path_factory.mktemp("e2e-fastapi"))
    services = AppServices(
        ingestion=DocumentIngestionService(stack.document_store),
        processing=DocumentProcessingService(
            document_store=stack.document_store,
            processing_store=stack.processing_store,
            require_eligibility=False,
        ),
        indexing=stack.indexing,
        pipeline=stack.pipeline,
        settings=AppSettings(project_root=stack.root),
    )
    app = create_app(settings=services.settings, services=services)
    return TestClient(app), stack


def test_real_fastapi_ask_verified(real_api_client) -> None:
    client, stack = real_api_client
    response = client.post(
        "/ask",
        json={"question": "How can I request academic leave?"},
        headers={"X-Request-ID": "e2e-fastapi-verified"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "verified"
    assert payload["answer"]
    assert payload["citations"]
    assert "NVIDIA_API_KEY" not in response.text
    assert "TELEGRAM_BOT_TOKEN" not in response.text
    citation_doc_ids = {item["document_id"] for item in payload["citations"]}
    assert stack.document_ids["academic_leave.txt"] in citation_doc_ids


def test_real_fastapi_ask_refusal(real_api_client) -> None:
    client, _stack = real_api_client
    response = client.post(
        "/ask",
        json={"question": "What is the university policy for traveling to Mars?"},
        headers={"X-Request-ID": "e2e-fastapi-refusal"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "refused"


def test_real_fastapi_status_reports_nvidia(real_api_client) -> None:
    client, _stack = real_api_client
    response = client.get("/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["rag_available"] is True
    assert payload["nvidia_reachable"] is True
    assert "NVIDIA_API_KEY" not in response.text
