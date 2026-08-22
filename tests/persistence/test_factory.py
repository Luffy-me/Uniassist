"""Tests for persistence factory selection."""

from __future__ import annotations

from pathlib import Path

from uniassist.persistence.config import StorageBackend
from uniassist.persistence.factory import build_persistence
from uniassist.rag.vector_store import JsonVectorStore


def test_build_persistence_defaults_to_local(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("UNIASSIST_STORAGE_BACKEND", raising=False)
    bundle = build_persistence(tmp_path)
    assert bundle.backend == StorageBackend.LOCAL
    assert isinstance(bundle.vector_store, JsonVectorStore)
