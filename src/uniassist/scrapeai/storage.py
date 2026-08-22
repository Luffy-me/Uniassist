"""Generic local document storage with hash-based deduplication."""

from __future__ import annotations

from pathlib import Path

from uniassist.scrapeai.hashing import sha256_hex


class StorageConflictError(Exception):
    """Raised when stored content would overwrite a different file."""


class DocumentStorage:
    """Store downloaded documents on the local filesystem."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def path_for_hash(self, digest: str) -> Path | None:
        """Return the existing file path for *digest*, if present."""
        for path in self.base_dir.glob(f"{digest}__*"):
            if sha256_hex(path.read_bytes()) == digest:
                return path
        return None

    def has_hash(self, digest: str) -> bool:
        """Return True when a file with *digest* already exists."""
        return self.path_for_hash(digest) is not None

    def store(self, content: bytes, filename: str) -> Path:
        """Persist *content* and return the destination path.

        Files are stored as ``<sha256>__<filename>`` to avoid collisions.
        If the same hash already exists, the existing path is returned.
        If a different hash would reuse the same destination name, an error
        is raised instead of silently overwriting data.
        """
        digest = sha256_hex(content)
        existing = self.path_for_hash(digest)
        if existing is not None:
            return existing

        destination = self.base_dir / f"{digest}__{filename}"
        if destination.exists():
            existing_hash = sha256_hex(destination.read_bytes())
            if existing_hash != digest:
                raise StorageConflictError(
                    f"refusing to overwrite {destination} with different content"
                )
            return destination

        destination.write_bytes(content)
        return destination
