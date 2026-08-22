"""NVIDIA NIM embedding provider."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from uniassist.ai.providers.nvidia_config import (
    nvidia_request_json,
    resolve_api_key,
    resolve_base_url,
    resolve_embedding_model,
    resolve_timeout_seconds,
)
from uniassist.ai.providers.nvidia_exceptions import NVIDIAAPIError


@dataclass(frozen=True)
class EmbeddingProviderInfo:
    """Metadata describing an embedding provider."""

    provider_name: str
    model_name: str
    dimension: int


class NVIDIAEmbeddingProvider:
    """Semantic embeddings via NVIDIA NIM POST /v1/embeddings."""

    provider_name = "nvidia"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        dimension: int | None = None,
    ) -> None:
        self._base_url = (base_url or resolve_base_url()).rstrip("/")
        self._api_key = (
            api_key if api_key is not None else resolve_api_key(self._base_url)
        )
        self._model = model or resolve_embedding_model(
            base_url=self._base_url,
            api_key=self._api_key,
        )
        self._timeout = timeout_seconds or resolve_timeout_seconds()
        self._dimension = dimension

    @property
    def info(self) -> EmbeddingProviderInfo:
        dim = self._dimension or 0
        return EmbeddingProviderInfo(
            provider_name=self.provider_name,
            model_name=self._model,
            dimension=dim,
        )

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._dimension = len(self.embed_text("dimension probe"))
        return self._dimension

    def embed_text(self, text: str) -> list[float]:
        return self._embed([text], input_type="query")[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embed(texts, input_type="passage")

    def _embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        payload: dict[str, Any] = {
            "model": self._model,
            "input": texts,
            "input_type": input_type,
            "encoding_format": "float",
        }
        result = nvidia_request_json(
            method="POST",
            url=f"{self._base_url}/embeddings",
            api_key=self._api_key,
            timeout_seconds=self._timeout,
            payload=payload,
        )
        vectors = self._parse_embedding_response(result)
        if self._dimension is None and vectors:
            self._dimension = len(vectors[0])
        return vectors

    def _parse_embedding_response(self, payload: dict[str, Any]) -> list[list[float]]:
        data = payload.get("data")
        if not isinstance(data, list):
            raise NVIDIAAPIError("NVIDIA embedding response missing data array")
        ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
        vectors: list[list[float]] = []
        for item in ordered:
            embedding = item.get("embedding")
            if not isinstance(embedding, list):
                raise NVIDIAAPIError("NVIDIA embedding response item missing embedding")
            vectors.append([float(value) for value in embedding])
        return vectors
