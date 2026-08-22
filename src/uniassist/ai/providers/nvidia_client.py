"""NVIDIA NIM API client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from uniassist.ai.providers.nvidia_config import (
    check_nvidia_health,
    list_model_ids,
    nvidia_request_json,
    resolve_api_key,
    resolve_base_url,
    resolve_chat_model,
    resolve_timeout_seconds,
)
from uniassist.ai.providers.nvidia_exceptions import (
    NVIDIAAPIError,
    NVIDIAAuthenticationError,
    NVIDIAConfigError,
    NVIDIARateLimitError,
    NVIDIATimeoutError,
)


@dataclass(frozen=True)
class NVIDIAClientConfig:
    """Configuration for the NVIDIA NIM HTTP client."""

    api_key: str
    base_url: str
    model: str
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> NVIDIAClientConfig:
        base_url = resolve_base_url()
        api_key = resolve_api_key(base_url)
        model = resolve_chat_model(base_url=base_url, api_key=api_key)
        timeout = resolve_timeout_seconds()
        return cls(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout,
        )


class NVIDIAClient:
    """Minimal HTTP client for NVIDIA NIM chat completions."""

    def __init__(self, config: NVIDIAClientConfig) -> None:
        self._config = config

    @property
    def model(self) -> str:
        return self._config.model

    @property
    def base_url(self) -> str:
        return self._config.base_url

    def list_models(self) -> list[str]:
        return list_model_ids(
            base_url=self._config.base_url,
            api_key=self._config.api_key,
            timeout_seconds=self._config.timeout_seconds,
        )

    def health_status(self):
        return check_nvidia_health(
            base_url=self._config.base_url,
            api_key=self._config.api_key,
            chat_model=self._config.model,
            timeout_seconds=self._config.timeout_seconds,
        )

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        response_format_json: bool = True,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Call POST /v1/chat/completions."""
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        return nvidia_request_json(
            method="POST",
            url=f"{self._config.base_url}/chat/completions",
            api_key=self._config.api_key,
            timeout_seconds=self._config.timeout_seconds,
            payload=payload,
        )


__all__ = [
    "NVIDIAClient",
    "NVIDIAClientConfig",
    "NVIDIAAPIError",
    "NVIDIAAuthenticationError",
    "NVIDIAConfigError",
    "NVIDIARateLimitError",
    "NVIDIATimeoutError",
]
