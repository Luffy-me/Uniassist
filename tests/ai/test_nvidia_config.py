"""Tests for shared NVIDIA configuration helpers."""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import patch

import pytest

from uniassist.ai.providers.nvidia_config import (
    LOCAL_NVIDIA_BASE_URL,
    check_nvidia_health,
    classify_model_ids,
    nvidia_request_json,
    resolve_api_key,
    resolve_base_url,
    resolve_chat_model,
)
from uniassist.ai.providers.nvidia_exceptions import NVIDIAConfigError


def test_resolve_base_url_prefers_nvidia_base_url(monkeypatch) -> None:
    monkeypatch.setenv("NVIDIA_BASE_URL", "http://127.0.0.1:8000/v1")
    monkeypatch.setenv("NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1")
    assert resolve_base_url() == "http://127.0.0.1:8000/v1"


def test_local_nim_allows_missing_api_key(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setenv("NVIDIA_BASE_URL", LOCAL_NVIDIA_BASE_URL)
    assert resolve_api_key(LOCAL_NVIDIA_BASE_URL) == ""


def test_hosted_nvidia_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(NVIDIAConfigError, match="NVIDIA_API_KEY"):
        resolve_api_key("https://integrate.api.nvidia.com/v1")


def test_classify_model_ids() -> None:
    chat, embed = classify_model_ids(
        ["meta/llama-3.1-8b-instruct", "nvidia/nv-embedqa-e5-v5"]
    )
    assert chat == ["meta/llama-3.1-8b-instruct"]
    assert embed == ["nvidia/nv-embedqa-e5-v5"]


def test_resolve_chat_model_uses_configured_value(monkeypatch) -> None:
    monkeypatch.setenv("NVIDIA_CHAT_MODEL", "meta/llama-3.1-8b-instruct")
    assert (
        resolve_chat_model(
            base_url=LOCAL_NVIDIA_BASE_URL,
            api_key="",
        )
        == "meta/llama-3.1-8b-instruct"
    )


def test_check_nvidia_health_reports_unreachable(monkeypatch) -> None:
    monkeypatch.setenv("NVIDIA_BASE_URL", LOCAL_NVIDIA_BASE_URL)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    def _fail(*args, **kwargs):
        from uniassist.ai.providers.nvidia_exceptions import NVIDIAAPIError

        raise NVIDIAAPIError("NVIDIA API network error: Connection refused")

    with patch(
        "uniassist.ai.providers.nvidia_config.list_model_ids",
        side_effect=_fail,
    ):
        status = check_nvidia_health()
    assert status.reachable is False
    assert "not running" in status.message.lower()


def test_nvidia_request_retries_transient_failure(monkeypatch) -> None:
    attempts = {"count": 0}

    class FakeResponse:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise urllib.error.HTTPError(
                url=request.full_url,
                code=503,
                msg="Service Unavailable",
                hdrs=None,
                fp=io.BytesIO(b"temporary"),
            )
        return FakeResponse(json.dumps({"ok": True}).encode("utf-8"))

    monkeypatch.setattr(
        "uniassist.ai.providers.nvidia_config.urllib.request.urlopen",
        fake_urlopen,
    )
    payload = nvidia_request_json(
        method="GET",
        url=f"{LOCAL_NVIDIA_BASE_URL}/models",
        api_key="",
        timeout_seconds=1.0,
    )
    assert payload == {"ok": True}
    assert attempts["count"] == 2
