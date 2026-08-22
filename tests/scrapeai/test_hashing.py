"""Tests for hashing utilities."""

from __future__ import annotations

from uniassist.scrapeai.hashing import sha256_hex


def test_sha256_calculation() -> None:
    digest = sha256_hex(b"hello")
    assert digest == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
