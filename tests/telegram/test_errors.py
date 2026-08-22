"""Tests for Telegram error mapping and safety messages."""

from __future__ import annotations

from uniassist.telegram.errors import (
    SERVICE_UNAVAILABLE_MESSAGE,
    UniAssistAPIError,
    UniAssistAPIResponseError,
    UniAssistAPIUnavailableError,
    map_api_error,
)


def test_map_api_error_status_codes() -> None:
    assert "rephrasing" in map_api_error(
        UniAssistAPIError("bad", status_code=422)
    ).text
    assert "offline" not in map_api_error(
        UniAssistAPIError("missing", status_code=404)
    ).text
    assert "busy" in map_api_error(
        UniAssistAPIError("conflict", status_code=409)
    ).text
    assert "too quickly" in map_api_error(
        UniAssistAPIError("limited", status_code=429)
    ).text
    assert map_api_error(
        UniAssistAPIError("down", status_code=503)
    ).text == SERVICE_UNAVAILABLE_MESSAGE
    assert map_api_error(
        UniAssistAPIError("fail", status_code=500)
    ).text == SERVICE_UNAVAILABLE_MESSAGE


def test_map_api_error_does_not_leak_internals() -> None:
    mapped = map_api_error(
        UniAssistAPIUnavailableError("connection refused to 127.0.0.1:8000")
    )
    assert "127.0.0.1" not in mapped.text
    assert "connection refused" not in mapped.text


def test_map_malformed_response_error() -> None:
    mapped = map_api_error(UniAssistAPIResponseError("invalid json"))
    assert mapped.text == SERVICE_UNAVAILABLE_MESSAGE
