"""Scrapy crawler integration for ScrapeAI."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from pathlib import Path
from typing import Any

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.http import Response
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import Spider

from uniassist.scrapeai.classifier import Classifier, default_classifier
from uniassist.scrapeai.config import SourceProfile
from uniassist.scrapeai.discovery import (
    identify_document_candidates,
    is_document_url,
    normalize_url,
    register_url,
)
from uniassist.scrapeai.downloader import DocumentDownloader
from uniassist.scrapeai.logging import get_logger, log_event
from uniassist.scrapeai.models import DocumentCandidate, DownloadResult, LinkCandidate
from uniassist.scrapeai.storage import DocumentStorage

logger = get_logger(__name__)


def build_scrapy_settings(profile: SourceProfile) -> dict[str, Any]:
    """Translate a :class:`SourceProfile` into Scrapy settings."""
    return {
        "ROBOTSTXT_OBEY": profile.respect_robots,
        "DOWNLOAD_DELAY": profile.request_delay,
        "AUTOTHROTTLE_ENABLED": False,
        "LOG_ENABLED": False,
        "USER_AGENT": "ScrapeAI/0.1 (+https://example.local/scrapeai)",
    }


class ScrapeAISpider(Spider):
    """Generic Scrapy spider that discovers and downloads documents."""

    name = "scrapeai"

    def __init__(
        self,
        profile: SourceProfile,
        storage: DocumentStorage,
        classifier: Classifier | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.profile = profile
        self.storage = storage
        self.classifier = classifier or default_classifier(
            profile.allowed_content_types
        )
        self.downloader = DocumentDownloader(storage)
        self.allowed_domains = list(profile.allowed_domains)
        self.start_urls = list(profile.seed_urls)
        self._seen_urls: set[str] = set()
        self._link_extractor = LinkExtractor(
            allow_domains=profile.allowed_domains,
            deny_extensions=["jpg", "jpeg", "png", "gif", "svg", "css", "js"],
        )
        self.download_results: list[DownloadResult] = []

    async def start(self) -> AsyncIterator[scrapy.Request]:
        for url in self.profile.seed_urls:
            normalized = register_url(url, self._seen_urls)
            yield scrapy.Request(normalized, callback=self.parse_page)

    def parse_page(self, response: Response) -> Iterable[scrapy.Request]:
        log_event(logger, 20, "page_parsed", url=response.url)
        links = self._extract_links(response)
        documents = identify_document_candidates(
            links,
            self.profile.allowed_content_types,
        )
        for candidate in documents:
            if not self.classifier.is_relevant(candidate):
                continue
            if is_duplicate_request(candidate.url, self._seen_urls):
                continue
            register_url(candidate.url, self._seen_urls)
            yield scrapy.Request(
                candidate.url,
                callback=self.parse_document,
                meta={"candidate": candidate},
            )

        for link in links:
            if is_document_url(link.url):
                continue
            if is_duplicate_request(link.url, self._seen_urls):
                continue
            register_url(link.url, self._seen_urls)
            yield scrapy.Request(link.url, callback=self.parse_page)

    def parse_document(self, response: Response) -> None:
        candidate: DocumentCandidate = response.meta["candidate"]
        result = self.downloader.process_response(candidate, response)
        self.download_results.append(result)

    def _extract_links(self, response: Response) -> list[LinkCandidate]:
        extracted = self._link_extractor.extract_links(response)
        links: list[LinkCandidate] = []
        for link in extracted:
            absolute = response.urljoin(link.url)
            links.append(
                LinkCandidate(
                    url=normalize_url(absolute),
                    source_url=response.url,
                    text=link.text or "",
                )
            )
        return links


def is_duplicate_request(url: str, seen: set[str]) -> bool:
    """Return True when the normalized URL was already scheduled."""
    return normalize_url(url) in seen


def run_crawler(
    profile: SourceProfile,
    storage_dir: Path,
    classifier: Classifier | None = None,
) -> list[DownloadResult]:
    """Run the ScrapeAI spider for a source profile."""
    storage = DocumentStorage(storage_dir)
    settings = build_scrapy_settings(profile)
    process = CrawlerProcess(settings=settings)
    crawler = process.create_crawler(ScrapeAISpider)
    process.crawl(
        crawler,
        profile=profile,
        storage=storage,
        classifier=classifier,
    )
    process.start()
    spider = crawler.spider
    if spider is None:
        return []
    return list(spider.download_results)
