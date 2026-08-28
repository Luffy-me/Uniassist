"""Tests for the Groq chat provider configuration and request contract."""

from __future__ import annotations

import pytest

from uniassist.ai.providers.groq import (
    GroqClient,
    GroqClientConfig,
    GroqConfigError,
)


def test_missing_groq_api_key_is_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(GroqConfigError, match="GROQ_API_KEY"):
        GroqClientConfig.from_env()


def test_chat_request_uses_strict_json_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def fake_request(**kwargs):
        captured.update(kwargs)
        return {"choices": [{"message": {"content": "{}"}}]}

    monkeypatch.setattr("uniassist.ai.providers.groq._request_json", fake_request)
    client = GroqClient(GroqClientConfig(api_key="test-key"))
    client.chat_completion([{"role": "user", "content": "hello"}])

    response_format = captured["payload"]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"]["required"] == [
        "answer",
        "insufficient_evidence",
        "claims",
    ]


def test_verification_request_uses_verification_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def fake_request(**kwargs):
        captured.update(kwargs)
        return {"choices": [{"message": {"content": "{}"}}]}

    monkeypatch.setattr("uniassist.ai.providers.groq._request_json", fake_request)
    client = GroqClient(GroqClientConfig(api_key="test-key"))
    client.chat_completion(
        [{"role": "user", "content": "verify"}], schema_name="verification"
    )

    assert captured["payload"]["response_format"]["json_schema"]["schema"][
        "required"
    ] == [
        "verified",
        "confidence",
        "supported_claims",
        "unsupported_claims",
        "contradictions",
        "citation_errors",
        "reasoning_summary",
    ]


def test_request_includes_a_stable_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self) -> bytes:
            return b"{}"

    def fake_urlopen(request, **_kwargs):
        captured["headers"] = dict(request.header_items())
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = GroqClient(GroqClientConfig(api_key="test-key"))
    client.chat_completion([{"role": "user", "content": "hello"}])

    assert captured["headers"]["User-agent"] == "UniAssist/1.0"
