"""FastAPI contract integration tests for the Telegram boundary."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import (
    MockAnswerPipeline,
    build_test_services,
    make_refusal_answer,
    make_verified_answer,
)
from uniassist.api.app import create_app
from uniassist.telegram.api_client import _parse_ask_response
from uniassist.telegram.errors import REFUSAL_MESSAGE
from uniassist.telegram.formatting import format_ask_result


@pytest.fixture
def api_client(project_root) -> TestClient:
    pipeline = MockAnswerPipeline(make_verified_answer())
    services = build_test_services(project_root, pipeline)
    app = create_app(services=services)
    return TestClient(app)


def test_telegram_boundary_verified_contract(api_client: TestClient) -> None:
    response = api_client.post(
        "/ask",
        json={"question": "Can I take academic leave?"},
        headers={"X-Request-ID": "telegram-req-1"},
    )
    assert response.status_code == 200
    payload = response.json()
    result = _parse_ask_response(payload, "telegram-req-1")
    formatted = format_ask_result(result)
    assert "Students may request academic leave." in formatted
    assert "Sources:" in formatted
    assert "Academic Leave Regulations" in formatted


def test_telegram_boundary_refusal_contract(project_root) -> None:
    pipeline = MockAnswerPipeline(make_refusal_answer())
    services = build_test_services(project_root, pipeline)
    client = TestClient(create_app(services=services))
    response = client.post(
        "/ask",
        json={"question": "Moon travel policy?"},
    )
    payload = response.json()
    result = _parse_ask_response(payload, payload["request_id"])
    formatted = format_ask_result(result)
    assert "No relevant evidence" in formatted or formatted == REFUSAL_MESSAGE


@pytest.mark.asyncio
async def test_optional_telegram_integration_skipped_by_default() -> None:
    if os.environ.get("UNIASSIST_RUN_TELEGRAM_INTEGRATION") != "1":
        pytest.skip("Telegram integration disabled")
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        pytest.skip("TELEGRAM_BOT_TOKEN not set")
