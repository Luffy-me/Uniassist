"""Path-safe encoding for Appwrite blob references.

``pathlib.Path`` treats ``://`` as a URI scheme and corrupts values like
``appwrite://bucket/file`` into ``appwrite:/bucket/file``. UniAssist stores
remote blob locations using a path-safe prefix instead.
"""

from __future__ import annotations

from pathlib import Path

REMOTE_PATH_PREFIX = "uniassist-remote"


def is_remote_blob_path(path: Path | str) -> bool:
    """Return whether *path* refers to an Appwrite-backed blob."""
    normalized = str(path).replace("\\", "/")
    return normalized.startswith(f"{REMOTE_PATH_PREFIX}/")


def encode_blob_path(blob_ref: str) -> Path:
    """Encode an ``appwrite://`` reference as a pathlib-safe ``Path``."""
    if blob_ref.startswith("appwrite://"):
        suffix = blob_ref.removeprefix("appwrite://")
        return Path(REMOTE_PATH_PREFIX) / suffix
    return Path(blob_ref)


def decode_blob_path(path: Path | str) -> str:
    """Decode a path-safe blob location back to ``appwrite://`` form."""
    normalized = str(path).replace("\\", "/")
    if normalized.startswith(f"{REMOTE_PATH_PREFIX}/"):
        suffix = normalized.removeprefix(f"{REMOTE_PATH_PREFIX}/")
        return f"appwrite://{suffix}"
    return normalize_blob_ref(normalized)


def normalize_blob_ref(blob_ref: str) -> str:
    """Normalize pathlib-corrupted Appwrite blob references."""
    if blob_ref.startswith("virtual://"):
        blob_ref = blob_ref.removeprefix("virtual://")
    if blob_ref.startswith("virtual:/"):
        blob_ref = blob_ref.removeprefix("virtual:/")
    if blob_ref.startswith("appwrite:/") and not blob_ref.startswith("appwrite://"):
        return "appwrite://" + blob_ref.removeprefix("appwrite:/")
    return blob_ref
