"""Content hashing utilities shared across UniAssist packages."""

from __future__ import annotations

import hashlib


def sha256_hex(content: bytes) -> str:
    """Return the SHA-256 hex digest of *content*."""
    return hashlib.sha256(content).hexdigest()
