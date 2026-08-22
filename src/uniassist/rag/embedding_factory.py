"""Embedding provider selection for production and development."""

from __future__ import annotations

import os

from uniassist.ai.providers.nvidia_config import is_hosted_base_url, resolve_base_url
from uniassist.rag.embeddings import DeterministicEmbeddingProvider, EmbeddingProvider
from uniassist.rag.nvidia_embeddings import NVIDIAEmbeddingProvider


def create_embedding_provider(
    *,
    prefer_nvidia: bool = True,
    force_deterministic: bool = False,
) -> EmbeddingProvider:
    """Return the best available embedding provider for the environment."""
    if force_deterministic:
        return DeterministicEmbeddingProvider()
    provider = os.environ.get("UNIASSIST_EMBEDDING_PROVIDER", "").strip().lower()
    if provider == "deterministic":
        return DeterministicEmbeddingProvider()
    if provider == "nvidia" or _should_use_nvidia(prefer_nvidia=prefer_nvidia):
        return NVIDIAEmbeddingProvider()
    return DeterministicEmbeddingProvider()


def _should_use_nvidia(*, prefer_nvidia: bool) -> bool:
    if not prefer_nvidia:
        return False
    if os.environ.get("NVIDIA_API_KEY", "").strip():
        return True
    base_url = resolve_base_url()
    return not is_hosted_base_url(base_url)


def default_min_score_for(provider: EmbeddingProvider) -> float:
    """Return a sensible default similarity threshold for a provider."""
    if getattr(provider, "provider_name", "") == "nvidia":
        return float(os.environ.get("UNIASSIST_MIN_SCORE", "0.35"))
    # Deterministic embeddings use a different similarity scale; production
    # MIN_SCORE must not leak into dev/test retrieval thresholds.
    return 0.0
