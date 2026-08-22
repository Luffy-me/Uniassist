"""Tests for URL normalization and deduplication."""

from __future__ import annotations

from uniassist.scrapeai.discovery import (
    is_duplicate_url,
    normalize_url,
    register_url,
)


def test_normalize_url_removes_fragment_and_lowercases_host() -> None:
    assert (
        normalize_url("HTTPS://Example.org/docs/file.PDF#section")
        == "https://example.org/docs/file.PDF"
    )


def test_normalize_url_sorts_query_parameters() -> None:
    first = normalize_url("https://example.org/search?b=2&a=1")
    second = normalize_url("https://example.org/search?a=1&b=2")
    assert first == second


def test_url_deduplication_tracks_normalized_urls() -> None:
    seen: set[str] = set()
    register_url("https://Example.org/a/", seen)
    assert is_duplicate_url("https://example.org/a", seen) is True
    assert is_duplicate_url("https://example.org/b", seen) is False
