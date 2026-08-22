"""Vector index metadata and compatibility checks."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

INDEX_VERSION = 2


@dataclass(frozen=True)
class IndexManifest:
    """Metadata describing how the vector index was built."""

    provider_name: str
    embedding_model: str
    dimension: int
    index_version: int = INDEX_VERSION
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(
                self,
                "created_at",
                datetime.now(UTC).isoformat(),
            )

    def to_dict(self) -> dict:
        return {
            "provider_name": self.provider_name,
            "embedding_model": self.embedding_model,
            "dimension": self.dimension,
            "index_version": self.index_version,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> IndexManifest:
        return cls(
            provider_name=str(data["provider_name"]),
            embedding_model=str(data["embedding_model"]),
            dimension=int(data["dimension"]),
            index_version=int(data.get("index_version", INDEX_VERSION)),
            created_at=str(data.get("created_at", "")),
        )

    def is_compatible_with(
        self,
        *,
        provider_name: str,
        embedding_model: str,
        dimension: int,
    ) -> bool:
        return (
            self.provider_name == provider_name
            and self.embedding_model == embedding_model
            and self.dimension == dimension
            and self.index_version == INDEX_VERSION
        )


class IndexCompatibilityError(ValueError):
    """Raised when indexing would corrupt an incompatible vector index."""


class IndexManifestStore:
    """Persist and load index manifest metadata."""

    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> IndexManifest | None:
        if not self.manifest_path.exists():
            return None
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return IndexManifest.from_dict(data)

    def save(self, manifest: IndexManifest) -> None:
        temp_path = self.manifest_path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, self.manifest_path)

    def clear(self) -> None:
        if self.manifest_path.exists():
            self.manifest_path.unlink()
