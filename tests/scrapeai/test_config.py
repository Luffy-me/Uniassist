"""Tests for source configuration."""

from __future__ import annotations

import pytest

from uniassist.scrapeai.config import SourceProfile
from uniassist.scrapeai.crawler import build_scrapy_settings


def test_source_profile_defaults_respect_robots() -> None:
    profile = SourceProfile(
        name="demo",
        seed_urls=["https://example.org/"],
        allowed_domains=["example.org"],
    )
    assert profile.respect_robots is True


def test_source_profile_validation_requires_seed_urls() -> None:
    with pytest.raises(ValueError, match="seed_urls"):
        SourceProfile(name="demo", seed_urls=[], allowed_domains=["example.org"])


def test_robots_configuration_is_passed_to_scrapy(
    sample_profile: SourceProfile,
) -> None:
    settings = build_scrapy_settings(sample_profile)
    assert settings["ROBOTSTXT_OBEY"] is True

    profile_without_robots = SourceProfile(
        name="demo",
        seed_urls=["https://example.org/"],
        allowed_domains=["example.org"],
        respect_robots=False,
    )
    disabled = build_scrapy_settings(profile_without_robots)
    assert disabled["ROBOTSTXT_OBEY"] is False
