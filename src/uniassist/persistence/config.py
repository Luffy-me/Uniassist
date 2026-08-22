"""Persistence and Appwrite configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum


class StorageBackend(StrEnum):
    """Supported persistence backends."""

    LOCAL = "local"
    APPWRITE = "appwrite"


class AppwriteConfigError(ValueError):
    """Raised when Appwrite configuration is missing or invalid."""


@dataclass(frozen=True)
class AppwriteConfig:
    """Appwrite Cloud connection settings (never log api_key)."""

    endpoint: str
    project_id: str
    api_key: str
    database_id: str
    documents_collection_id: str
    processing_collection_id: str
    chunks_collection_id: str
    raw_bucket_id: str
    processed_bucket_id: str

    @classmethod
    def from_env(cls) -> AppwriteConfig:
        return cls(
            endpoint=_required("APPWRITE_ENDPOINT"),
            project_id=_required("APPWRITE_PROJECT_ID"),
            api_key=_required("APPWRITE_API_KEY"),
            database_id=_required("APPWRITE_DATABASE_ID"),
            documents_collection_id=_required("APPWRITE_DOCUMENTS_COLLECTION_ID"),
            processing_collection_id=_required("APPWRITE_PROCESSING_COLLECTION_ID"),
            chunks_collection_id=_required("APPWRITE_CHUNKS_COLLECTION_ID"),
            raw_bucket_id=_required("APPWRITE_RAW_BUCKET_ID"),
            processed_bucket_id=_required("APPWRITE_PROCESSED_BUCKET_ID"),
        )

    @classmethod
    def try_from_env(cls) -> AppwriteConfig | None:
        required = (
            "APPWRITE_ENDPOINT",
            "APPWRITE_PROJECT_ID",
            "APPWRITE_API_KEY",
            "APPWRITE_DATABASE_ID",
            "APPWRITE_DOCUMENTS_COLLECTION_ID",
            "APPWRITE_PROCESSING_COLLECTION_ID",
            "APPWRITE_CHUNKS_COLLECTION_ID",
            "APPWRITE_RAW_BUCKET_ID",
            "APPWRITE_PROCESSED_BUCKET_ID",
        )
        if not all(os.environ.get(name, "").strip() for name in required):
            return None
        return cls.from_env()

    def validate_for_production(self) -> None:
        missing = [
            name
            for name, value in (
                ("APPWRITE_ENDPOINT", self.endpoint),
                ("APPWRITE_PROJECT_ID", self.project_id),
                ("APPWRITE_API_KEY", self.api_key),
                ("APPWRITE_DATABASE_ID", self.database_id),
                ("APPWRITE_DOCUMENTS_COLLECTION_ID", self.documents_collection_id),
                ("APPWRITE_PROCESSING_COLLECTION_ID", self.processing_collection_id),
                ("APPWRITE_CHUNKS_COLLECTION_ID", self.chunks_collection_id),
                ("APPWRITE_RAW_BUCKET_ID", self.raw_bucket_id),
                ("APPWRITE_PROCESSED_BUCKET_ID", self.processed_bucket_id),
            )
            if not str(value).strip()
        ]
        if missing:
            raise AppwriteConfigError(
                "Appwrite production configuration is incomplete. "
                f"Missing: {', '.join(missing)}"
            )

    def redacted_summary(self) -> dict[str, str]:
        """Safe summary for logs and status endpoints."""
        return {
            "endpoint": self.endpoint,
            "project_id": self.project_id,
            "database_id": self.database_id,
            "raw_bucket_id": self.raw_bucket_id,
            "processed_bucket_id": self.processed_bucket_id,
            "api_key_configured": "yes" if self.api_key else "no",
        }


def resolve_storage_backend() -> StorageBackend:
    raw = os.environ.get("UNIASSIST_STORAGE_BACKEND", StorageBackend.LOCAL.value)
    normalized = raw.strip().lower()
    try:
        return StorageBackend(normalized)
    except ValueError as exc:
        raise AppwriteConfigError(
            f"UNIASSIST_STORAGE_BACKEND must be 'local' or 'appwrite', got {raw!r}"
        ) from exc


def resolve_data_dir(project_root: os.PathLike[str] | None = None) -> str:
    from pathlib import Path

    if os.environ.get("UNIASSIST_DATA_DIR", "").strip():
        return os.environ["UNIASSIST_DATA_DIR"].strip()
    root = Path(project_root) if project_root is not None else Path.cwd()
    return str(root / "data")


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise AppwriteConfigError(f"{name} is required for Appwrite persistence")
    return value
