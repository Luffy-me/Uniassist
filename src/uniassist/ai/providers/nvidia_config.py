"""Shared NVIDIA NIM configuration, discovery, health, and HTTP helpers."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from uniassist.ai.providers.nvidia_exceptions import (
    NVIDIAAPIError,
    NVIDIAAuthenticationError,
    NVIDIAConfigError,
    NVIDIARateLimitError,
    NVIDIATimeoutError,
)

HOSTED_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
LOCAL_NVIDIA_BASE_URL = "http://localhost:8000/v1"
DEFAULT_CHAT_MODEL = "meta/llama-3.1-8b-instruct"
DEFAULT_EMBEDDING_MODEL = "nvidia/nv-embedqa-e5-v5"
MAX_RETRIES = 3
RETRYABLE_STATUS_CODES = {502, 503, 504}


@dataclass(frozen=True)
class NVIDIAHealthStatus:
    """Safe NVIDIA connectivity and model availability status."""

    reachable: bool
    message: str
    base_url: str
    chat_model: str | None = None
    embedding_model: str | None = None
    chat_model_available: bool | None = None
    embedding_model_available: bool | None = None
    available_models: tuple[str, ...] = ()


def resolve_base_url() -> str:
    """Resolve NVIDIA OpenAI-compatible base URL."""
    for key in ("NVIDIA_BASE_URL", "NVIDIA_API_BASE"):
        value = os.environ.get(key, "").strip()
        if value:
            return value.rstrip("/")
    return LOCAL_NVIDIA_BASE_URL


def is_hosted_base_url(base_url: str) -> bool:
    normalized = base_url.rstrip("/").lower()
    return "integrate.api.nvidia.com" in normalized


def resolve_timeout_seconds() -> float:
    return float(os.environ.get("NVIDIA_TIMEOUT_SECONDS", "60"))


def resolve_api_key(base_url: str | None = None) -> str:
    """Return API key; required for hosted NVIDIA, optional for local NIM."""
    api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    resolved_base = base_url or resolve_base_url()
    if api_key:
        return api_key
    if is_hosted_base_url(resolved_base):
        raise NVIDIAConfigError(
            "NVIDIA_API_KEY is required for hosted NVIDIA API "
            f"({HOSTED_NVIDIA_BASE_URL})."
        )
    return ""


def resolve_chat_model(*, base_url: str, api_key: str) -> str:
    configured = (
        os.environ.get("NVIDIA_CHAT_MODEL", "").strip()
        or os.environ.get("NVIDIA_MODEL", "").strip()
    )
    if configured:
        _validate_model_available(
            configured,
            base_url=base_url,
            api_key=api_key,
            purpose="chat",
        )
        return configured
    chat_models, _ = _discover_models(base_url=base_url, api_key=api_key)
    if len(chat_models) == 1:
        return chat_models[0]
    if not chat_models:
        raise NVIDIAConfigError(
            "NVIDIA chat model is not configured and no chat models were "
            "discovered. Set NVIDIA_CHAT_MODEL after inspecting "
            f"GET {base_url}/models."
        )
    raise NVIDIAConfigError(
        "Multiple NVIDIA chat models are available. Set NVIDIA_CHAT_MODEL "
        f"explicitly. Available chat models: {', '.join(chat_models)}"
    )


def resolve_embedding_model(*, base_url: str, api_key: str) -> str:
    configured = os.environ.get("NVIDIA_EMBEDDING_MODEL", "").strip()
    if configured:
        _validate_model_available(
            configured,
            base_url=base_url,
            api_key=api_key,
            purpose="embedding",
        )
        return configured
    _, embedding_models = _discover_models(base_url=base_url, api_key=api_key)
    if len(embedding_models) == 1:
        return embedding_models[0]
    if not embedding_models:
        raise NVIDIAConfigError(
            "NVIDIA embedding model is not configured and no embedding models "
            "were discovered. Set NVIDIA_EMBEDDING_MODEL after inspecting "
            f"GET {base_url}/models."
        )
    raise NVIDIAConfigError(
        "Multiple NVIDIA embedding models are available. Set "
        f"NVIDIA_EMBEDDING_MODEL explicitly. Available embedding models: "
        f"{', '.join(embedding_models)}"
    )


def list_model_ids(*, base_url: str, api_key: str, timeout_seconds: float) -> list[str]:
    payload = nvidia_request_json(
        method="GET",
        url=f"{base_url.rstrip('/')}/models",
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )
    data = payload.get("data")
    if not isinstance(data, list):
        raise NVIDIAAPIError("NVIDIA models response missing data array")
    model_ids: list[str] = []
    for item in data:
        if isinstance(item, dict):
            model_id = item.get("id")
            if isinstance(model_id, str) and model_id.strip():
                model_ids.append(model_id.strip())
    return model_ids


def classify_model_ids(model_ids: list[str]) -> tuple[list[str], list[str]]:
    chat_models: list[str] = []
    embedding_models: list[str] = []
    for model_id in model_ids:
        lowered = model_id.lower()
        if "embed" in lowered:
            embedding_models.append(model_id)
        else:
            chat_models.append(model_id)
    return chat_models, embedding_models


def check_nvidia_health(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    chat_model: str | None = None,
    embedding_model: str | None = None,
    timeout_seconds: float | None = None,
) -> NVIDIAHealthStatus:
    resolved_base = (base_url or resolve_base_url()).rstrip("/")
    resolved_timeout = timeout_seconds or resolve_timeout_seconds()
    try:
        resolved_key = (
            api_key if api_key is not None else resolve_api_key(resolved_base)
        )
    except NVIDIAConfigError as exc:
        return NVIDIAHealthStatus(
            reachable=False,
            message=str(exc),
            base_url=resolved_base,
        )

    try:
        model_ids = list_model_ids(
            base_url=resolved_base,
            api_key=resolved_key,
            timeout_seconds=resolved_timeout,
        )
    except (NVIDIAAPIError, NVIDIAAuthenticationError, NVIDIATimeoutError) as exc:
        message = str(exc)
        if "Connection refused" in message or "network error" in message.lower():
            message = "NVIDIA NIM is not running."
        return NVIDIAHealthStatus(
            reachable=False,
            message=message,
            base_url=resolved_base,
        )

    chat_candidates, embedding_candidates = classify_model_ids(model_ids)
    resolved_chat = chat_model
    resolved_embedding = embedding_model
    if resolved_chat is None:
        resolved_chat = (
            os.environ.get("NVIDIA_CHAT_MODEL", "").strip()
            or os.environ.get("NVIDIA_MODEL", "").strip()
            or None
        )
    if resolved_embedding is None:
        resolved_embedding = (
            os.environ.get("NVIDIA_EMBEDDING_MODEL", "").strip() or None
        )
    chat_available: bool | None = None
    embedding_available: bool | None = None

    if resolved_chat:
        chat_available = resolved_chat in model_ids
    if resolved_embedding:
        embedding_available = resolved_embedding in model_ids

    if chat_available is False or embedding_available is False:
        missing = []
        if chat_available is False:
            missing.append(f"chat model '{resolved_chat}'")
        if embedding_available is False:
            missing.append(f"embedding model '{resolved_embedding}'")
        return NVIDIAHealthStatus(
            reachable=True,
            message=(
                f"Configured {' and '.join(missing)} not available from NVIDIA NIM."
            ),
            base_url=resolved_base,
            chat_model=resolved_chat,
            embedding_model=resolved_embedding,
            chat_model_available=chat_available,
            embedding_model_available=embedding_available,
            available_models=tuple(model_ids),
        )

    return NVIDIAHealthStatus(
        reachable=True,
        message="NVIDIA NIM is reachable.",
        base_url=resolved_base,
        chat_model=resolved_chat,
        embedding_model=resolved_embedding,
        chat_model_available=chat_available,
        embedding_model_available=embedding_available,
        available_models=tuple(model_ids),
    )


def nvidia_request_json(
    *,
    method: str,
    url: str,
    api_key: str,
    timeout_seconds: float,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers)

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8")
                parsed = json.loads(body)
                if not isinstance(parsed, dict):
                    raise NVIDIAAPIError("NVIDIA response was not a JSON object")
                return parsed
        except urllib.error.HTTPError as exc:
            if exc.code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                time.sleep(0.5 * (2**attempt))
                last_error = exc
                continue
            _raise_for_http_error(exc)
            raise
        except TimeoutError as exc:
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.5 * (2**attempt))
                last_error = exc
                continue
            raise NVIDIATimeoutError("NVIDIA API request timed out") from exc
        except urllib.error.URLError as exc:
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.5 * (2**attempt))
                last_error = exc
                continue
            if "timed out" in str(exc.reason).lower():
                raise NVIDIATimeoutError("NVIDIA API request timed out") from exc
            raise NVIDIAAPIError(f"NVIDIA API network error: {exc.reason}") from exc

    if isinstance(last_error, urllib.error.HTTPError):
        _raise_for_http_error(last_error)
    if isinstance(last_error, TimeoutError):
        raise NVIDIATimeoutError("NVIDIA API request timed out") from last_error
    if isinstance(last_error, urllib.error.URLError):
        raise NVIDIAAPIError(
            f"NVIDIA API network error: {last_error.reason}"
        ) from last_error
    raise NVIDIAAPIError("NVIDIA API request failed after retries")


def _discover_models(*, base_url: str, api_key: str) -> tuple[list[str], list[str]]:
    timeout = resolve_timeout_seconds()
    model_ids = list_model_ids(
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=timeout,
    )
    return classify_model_ids(model_ids)


def _validate_model_available(
    model_id: str,
    *,
    base_url: str,
    api_key: str,
    purpose: str,
) -> None:
    try:
        model_ids = list_model_ids(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=resolve_timeout_seconds(),
        )
    except (NVIDIAAPIError, NVIDIAAuthenticationError, NVIDIATimeoutError):
        return
    if model_id not in model_ids:
        raise NVIDIAConfigError(
            f"Configured NVIDIA {purpose} model '{model_id}' is not available. "
            f"Inspect GET {base_url}/models."
        )


def _raise_for_http_error(exc: urllib.error.HTTPError) -> None:
    body = exc.read().decode("utf-8", errors="replace")
    if exc.code in {401, 403}:
        raise NVIDIAAuthenticationError(
            "NVIDIA API authentication failed. Check NVIDIA_API_KEY."
        ) from exc
    if exc.code == 429:
        raise NVIDIARateLimitError("NVIDIA API rate limit exceeded") from exc
    if exc.code == 404:
        raise NVIDIAAPIError("NVIDIA model or endpoint not found") from exc
    raise NVIDIAAPIError(f"NVIDIA API error {exc.code}: {body[:500]}") from exc
