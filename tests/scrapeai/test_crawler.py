"""Tests for the Scrapy crawler integration."""

from __future__ import annotations

from pathlib import Path

import pytest
from scrapy.http import HtmlResponse, Request, TextResponse

from uniassist.scrapeai.classifier import ClassificationRule, RuleBasedClassifier
from uniassist.scrapeai.config import SourceProfile
from uniassist.scrapeai.crawler import ScrapeAISpider, build_scrapy_settings
from uniassist.scrapeai.storage import DocumentStorage


@pytest.fixture
def spider(tmp_path: Path) -> ScrapeAISpider:
    profile = SourceProfile(
        name="example-source",
        seed_urls=["https://example.org/"],
        allowed_domains=["example.org"],
        respect_robots=True,
        allowed_content_types=["application/pdf"],
        request_delay=0.0,
    )
    storage = DocumentStorage(tmp_path)
    classifier = RuleBasedClassifier(rules=[ClassificationRule(extensions={".pdf"})])
    return ScrapeAISpider(profile=profile, storage=storage, classifier=classifier)


def test_build_scrapy_settings_uses_request_delay(
    sample_profile: SourceProfile,
) -> None:
    settings = build_scrapy_settings(sample_profile)
    assert settings["DOWNLOAD_DELAY"] == 0.0


def test_spider_discovers_pdf_requests(spider: ScrapeAISpider) -> None:
    html = """
    <html>
      <body>
        <a href="/docs/report.pdf">Annual report</a>
        <a href="/about">About us</a>
      </body>
    </html>
    """
    response = HtmlResponse(
        url="https://example.org/",
        body=html.encode(),
        encoding="utf-8",
    )

    requests = list(spider.parse_page(response))
    pdf_requests = [req for req in requests if req.url.endswith(".pdf")]

    assert len(pdf_requests) == 1
    assert pdf_requests[0].url == "https://example.org/docs/report.pdf"


def test_spider_downloads_document(spider: ScrapeAISpider) -> None:
    from uniassist.scrapeai.models import DocumentCandidate

    candidate = DocumentCandidate(
        url="https://example.org/docs/report.pdf",
        source_url="https://example.org/",
        content_type="application/pdf",
        filename="report.pdf",
    )
    request = Request(
        url="https://example.org/docs/report.pdf",
        meta={"candidate": candidate},
    )
    response = TextResponse(
        url="https://example.org/docs/report.pdf",
        body=b"%PDF-1.4 test",
        headers={b"Content-Type": [b"application/pdf"]},
        request=request,
    )

    spider.parse_document(response)

    assert len(spider.download_results) == 1
    result = spider.download_results[0]
    assert result.success is True
    assert result.metadata is not None
    assert result.metadata.filename == "report.pdf"
