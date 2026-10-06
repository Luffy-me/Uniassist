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


def test_transient_groq_errors_are_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import urllib.error

    from uniassist.ai.providers import groq

    calls = {"count": 0}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self) -> bytes:
            return b'{"ok": true}'

    def fake_urlopen(request, **_kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise urllib.error.HTTPError(
                request.full_url, 429, "slow down", {}, io.BytesIO(b"rate limited")
            )
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(groq, "_BACKOFF_SECONDS", 0.0)
    result = groq._request_json(
        url="https://example.test", api_key="k", timeout_seconds=1, payload={}
    )
    assert result == {"ok": True}
    assert calls["count"] == 3


def test_client_errors_are_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import urllib.error

    from uniassist.ai.providers import groq

    calls = {"count": 0}

    def fake_urlopen(request, **_kwargs):
        calls["count"] += 1
        raise urllib.error.HTTPError(
            request.full_url, 400, "bad", {}, io.BytesIO(b"bad request")
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(groq.GroqAPIError):
        groq._request_json(
            url="https://example.test", api_key="k", timeout_seconds=1, payload={}
        )
    assert calls["count"] == 1
