"""Tests for UniAssist API client."""

from __future__ import annotations

import json

import httpx
import pytest

from uniassist.telegram.api_client import UniAssistAPIClient
from uniassist.telegram.errors import (
    UniAssistAPIError,
    UniAssistAPIResponseError,
    UniAssistAPIUnavailableError,
)


@pytest.mark.asyncio
async def test_ask_parses_verified_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Request-ID"] == "req-123"
        assert json.loads(request.content) == {"question": "Can I take academic leave?"}
        return httpx.Response(
            200,
            json={
                "request_id": "req-123",
                "status": "verified",
                "answer": "Students may request academic leave.",
                "citations": [
                    {
                        "chunk_id": "c1",
                        "document_id": "d1",
                        "title": "Academic Leave Regulations",
                        "page_number": 4,
                        "section": "2.1",
                        "source": "TEST",
                        "source_url": "https://example.org",
                        "label": "Academic Leave Regulations — p. 4",
                    }
                ],
                "verification": {"verified": True, "confidence": 1.0},
            },
            headers={"X-Request-ID": "req-123"},
        )

    transport = httpx.MockTransport(handler)
    client = UniAssistAPIClient(
        base_url="http://testserver",
        _external_client=httpx.AsyncClient(transport=transport),
    )
    result = await client.ask(
        "Can I take academic leave?",
        request_id="req-123",
    )
    assert result.status == "verified"
    assert result.answer == "Students may request academic leave."
    assert result.citations[0].title == "Academic Leave Regulations"


@pytest.mark.asyncio
async def test_ask_parses_refusal_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "request_id": "req-refused",
                "status": "refused",
                "message": "No relevant evidence.",
                "verification": {"verified": False, "confidence": 0.0},
            },
        )
    )
    client = UniAssistAPIClient(
        base_url="http://testserver",
        _external_client=httpx.AsyncClient(transport=transport),
    )
    result = await client.ask("Moon travel policy?")
    assert result.status == "refused"
    assert result.message == "No relevant evidence."


@pytest.mark.asyncio
async def test_ask_maps_service_unavailable() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            503,
            json={
                "request_id": "req-503",
                "error": "service_unavailable",
                "detail": "Unavailable",
            },
        )
    )
    client = UniAssistAPIClient(
        base_url="http://testserver",
        _external_client=httpx.AsyncClient(transport=transport),
    )
    with pytest.raises(UniAssistAPIError) as exc:
        await client.ask("Question?")
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_ask_handles_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    client = UniAssistAPIClient(
        base_url="http://testserver",
        _external_client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            timeout=0.1,
        ),
    )
    with pytest.raises(UniAssistAPIUnavailableError):
        await client.ask("Question?")


@pytest.mark.asyncio
async def test_ask_rejects_malformed_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"status": "unknown"})
    )
    client = UniAssistAPIClient(
        base_url="http://testserver",
        _external_client=httpx.AsyncClient(transport=transport),
    )
    with pytest.raises(UniAssistAPIResponseError):
        await client.ask("Question?")
