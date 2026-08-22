"""Shared fixtures for ScrapeAI tests."""

from __future__ import annotations

import pytest

from uniassist.scrapeai.config import SourceProfile


@pytest.fixture
def sample_profile() -> SourceProfile:
    return SourceProfile(
        name="example-source",
        seed_urls=["https://example.org/"],
        allowed_domains=["example.org"],
        respect_robots=True,
        allowed_content_types=["application/pdf"],
        request_delay=0.0,
    )


SAMPLE_HTML = """
<html>
  <body>
    <a href="/docs/report.pdf">Annual report</a>
    <a href="/about">About us</a>
    <a href="https://other.example.org/external.pdf">External PDF</a>
  </body>
</html>
"""
