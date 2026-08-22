"""Tests for persistence configuration."""

from __future__ import annotations

import pytest

from uniassist.persistence.config import (
    AppwriteConfig,
    AppwriteConfigError,
    StorageBackend,
    resolve_storage_backend,
)


def test_default_storage_backend_is_local(monkeypatch) -> None:
    monkeypatch.delenv("UNIASSIST_STORAGE_BACKEND", raising=False)
    assert resolve_storage_backend() == StorageBackend.LOCAL


def test_invalid_storage_backend_raises(monkeypatch) -> None:
    monkeypatch.setenv("UNIASSIST_STORAGE_BACKEND", "mongodb")
    with pytest.raises(AppwriteConfigError, match="UNIASSIST_STORAGE_BACKEND"):
        resolve_storage_backend()


def test_appwrite_config_requires_all_variables(monkeypatch) -> None:
    monkeypatch.setenv("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")
    monkeypatch.delenv("APPWRITE_API_KEY", raising=False)
    with pytest.raises(AppwriteConfigError):
        AppwriteConfig.from_env()


def test_appwrite_config_redacted_summary_never_includes_key(monkeypatch) -> None:
    monkeypatch.setenv("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")
    monkeypatch.setenv("APPWRITE_PROJECT_ID", "project")
    monkeypatch.setenv("APPWRITE_API_KEY", "secret-key")
    monkeypatch.setenv("APPWRITE_DATABASE_ID", "db")
    monkeypatch.setenv("APPWRITE_DOCUMENTS_COLLECTION_ID", "docs")
    monkeypatch.setenv("APPWRITE_PROCESSING_COLLECTION_ID", "proc")
    monkeypatch.setenv("APPWRITE_CHUNKS_COLLECTION_ID", "chunks")
    monkeypatch.setenv("APPWRITE_RAW_BUCKET_ID", "raw")
    monkeypatch.setenv("APPWRITE_PROCESSED_BUCKET_ID", "processed")
    summary = AppwriteConfig.from_env().redacted_summary()
    assert "secret-key" not in str(summary)
    assert summary["api_key_configured"] == "yes"
