"""Blob storage abstraction for raw and processed artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from uniassist.core.hashing import sha256_hex
from uniassist.documents.exceptions import StorageConflictError
from uniassist.documents.validation import sanitize_filename


class DocumentBlobStore(Protocol):
    """Store immutable document blobs outside the metadata database."""

    def save(self, content: bytes, filename: str, *, digest: str | None = None) -> str:
        """Persist content and return a provider-specific blob reference."""

    def read(self, blob_ref: str) -> bytes:
        """Read blob bytes by reference."""

    def exists(self, blob_ref: str) -> bool:
        """Return whether the blob reference exists."""

    def delete(self, blob_ref: str) -> None:
        """Delete a blob when safe to do so."""


class LocalBlobStore:
    """Filesystem blob store with SHA-256 deduplication."""

    def __init__(self, raw_dir: Path) -> None:
        self.raw_dir = raw_dir
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def save(self, content: bytes, filename: str, *, digest: str | None = None) -> str:
        resolved_digest = digest or sha256_hex(content)
        existing = self._path_for_hash(resolved_digest)
        if existing is not None:
            return str(existing)

        safe_name = sanitize_filename(filename)
        destination = self.raw_dir / f"{resolved_digest}__{safe_name}"
        if destination.exists():
            existing_hash = sha256_hex(destination.read_bytes())
            if existing_hash != resolved_digest:
                raise StorageConflictError(
                    f"refusing to overwrite {destination} with different content"
                )
            return str(destination)

        destination.write_bytes(content)
        return str(destination)

    def read(self, blob_ref: str) -> bytes:
        path = Path(blob_ref)
        return path.read_bytes()

    def exists(self, blob_ref: str) -> bool:
        return Path(blob_ref).exists()

    def delete(self, blob_ref: str) -> None:
        path = Path(blob_ref)
        if path.exists():
            path.unlink()

    def _path_for_hash(self, digest: str) -> Path | None:
        for path in self.raw_dir.glob(f"{digest}__*"):
            if sha256_hex(path.read_bytes()) == digest:
                return path
        return None
