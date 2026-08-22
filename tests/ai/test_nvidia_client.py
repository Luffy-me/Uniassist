"""Tests for NVIDIA client configuration."""

from __future__ import annotations

import pytest

from uniassist.ai.providers.nvidia_client import NVIDIAClientConfig
from uniassist.ai.providers.nvidia_exceptions import NVIDIAConfigError


def test_hosted_missing_api_key_raises_clear_error(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("NVIDIA_CHAT_MODEL", "meta/llama-3.1-8b-instruct")
    with pytest.raises(NVIDIAConfigError, match="NVIDIA_API_KEY"):
        NVIDIAClientConfig.from_env()


def test_local_nim_allows_missing_api_key_with_configured_model(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setenv("NVIDIA_BASE_URL", "http://localhost:8000/v1")
    monkeypatch.setenv("NVIDIA_CHAT_MODEL", "meta/llama-3.1-8b-instruct")
    config = NVIDIAClientConfig.from_env()
    assert config.api_key == ""
    assert config.base_url == "http://localhost:8000/v1"
    assert config.model == "meta/llama-3.1-8b-instruct"
