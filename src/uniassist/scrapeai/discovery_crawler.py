"""Discovery-only Scrapy crawler for dry-run reporting."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.http import Response
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import Spider

from uniassist.scrapeai.classifier import ClassificationStatus, TriStateClassifier
from uniassist.scrapeai.config import SourceProfile
from uniassist.scrapeai.crawler import build_scrapy_settings, is_duplicate_request
from uniassist.scrapeai.discovery import (
    identify_document_candidates,
    is_document_url,
    is_pdf_url,
    normalize_url,
    register_url,
)
from uniassist.scrapeai.discovery_report import DiscoveryReport, ReportedCandidate
from uniassist.scrapeai.logging import get_logger, log_event
from uniassist.scrapeai.models import DocumentCandidate, LinkCandidate

logger = get_logger(__name__)

USER_AGENT = "ScrapeAI/0.1 (+https://example.local/scrapeai)"


class RobotsChecker:
    """Cache robots.txt parsers per host."""

    def __init__(self, user_agent: str = USER_AGENT) -> None:
        self._user_agent = user_agent
        self._parsers: dict[str, RobotFileParser] = {}

    def is_allowed(self, url: str, respect_robots: bool) -> bool:
        if not respect_robots:
            return True
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        host = parsed.netloc.lower()
        parser = self._parsers.get(host)
        if parser is None:
            parser = RobotFileParser()
            parser.set_url(f"{parsed.scheme}://{host}/robots.txt")
            try:
                parser.read()
            except OSError:
                return True
            self._parsers[host] = parser
        return parser.can_fetch(self._user_agent, url)


class DiscoverySpider(Spider):
    """Crawl pages and classify document candidates without downloading files."""

    name = "scrapeai-discovery"

    def __init__(
        self,
        profile: SourceProfile,
        classifier: TriStateClassifier,
        report: DiscoveryReport,
        robots_checker: RobotsChecker,
        max_pages: int = 100,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.profile = profile
        self.classifier = classifier
        self.report = report
        self.robots_checker = robots_checker
        self.max_pages = max_pages
        self.allowed_domains = list(profile.allowed_domains)
        self.start_urls = list(profile.seed_urls)
        self._seen_urls: set[str] = set()
        self._seen_links: set[str] = set()
        self._candidate_index: dict[str, ReportedCandidate] = {}
        self._link_extractor = LinkExtractor(
            allow_domains=profile.allowed_domains,
            deny_extensions=["jpg", "jpeg", "png", "gif", "svg", "css", "js"],
        )

    async def start(self) -> AsyncIterator[scrapy.Request]:
        for url in self.profile.seed_urls:
            if not self.robots_checker.is_allowed(url, self.profile.respect_robots):
                self._record_robots_blocked(url)
                continue
            normalized = register_url(url, self._seen_urls)
            yield scrapy.Request(normalized, callback=self.parse_page)

    def parse_page(self, response: Response) -> Iterable[scrapy.Request]:
        if len(self.report.pages_visited) >= self.max_pages:
            return

        self.report.pages_visited.append(response.url)
        log_event(logger, 20, "discovery_page_parsed", url=response.url)

        links = self._extract_links(response)
        for link in links:
            self._record_link(link)

        documents = identify_document_candidates(
            links,
            self.profile.allowed_content_types,
        )
        link_text_by_url = {normalize_url(link.url): link.text for link in links}
        for candidate in documents:
            link_text = link_text_by_url.get(candidate.url, "")
            self._record_document_candidate(candidate, link_text)

        if len(self.report.pages_visited) >= self.max_pages:
            return

        for link in links:
            if is_document_url(link.url):
                continue
            if is_duplicate_request(link.url, self._seen_urls):
                self._record_duplicate(link.url)
                continue
            if not self.robots_checker.is_allowed(
                link.url,
                self.profile.respect_robots,
            ):
                self._record_robots_blocked(link.url)
                continue
            register_url(link.url, self._seen_urls)
            yield scrapy.Request(link.url, callback=self.parse_page)

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

    def _record_link(self, link: LinkCandidate) -> None:
        normalized = normalize_url(link.url)
        if normalized in self._seen_links:
            return
        self._seen_links.add(normalized)
        self.report.links_discovered.append(
            {
                "url": link.url,
                "source_url": link.source_url,
                "text": link.text,
            }
        )

    def _record_document_candidate(
        self,
        candidate: DocumentCandidate,
        link_text: str,
    ) -> None:
        normalized = normalize_url(candidate.url)
        if normalized in self._candidate_index:
            existing = self._candidate_index[normalized]
            if candidate.source_url not in existing.source_urls:
                existing.source_urls.append(candidate.source_url)
            self._record_duplicate(candidate.url)
            return

        if not self.robots_checker.is_allowed(
            candidate.url,
            self.profile.respect_robots,
        ):
            self._record_robots_blocked(candidate.url)
            reported = ReportedCandidate(
                url=candidate.url,
                source_urls=[candidate.source_url],
                link_text=link_text,
                content_type=candidate.content_type,
                filename=candidate.filename,
                classification=ClassificationStatus.REVIEW.value,
                resolution_status="robots_blocked",
                is_direct_pdf=is_pdf_url(candidate.url),
            )
            self._candidate_index[normalized] = reported
            self.report.document_candidates.append(reported)
            self.report.review_candidates.append(reported)
            return

        status = self.classifier.classify(candidate, link_text=link_text)
        resolution_status = "discovered"
        if is_pdf_url(candidate.url):
            resolution_status = "direct_pdf"
            if candidate.url not in self.report.direct_pdf_urls:
                self.report.direct_pdf_urls.append(candidate.url)
        elif is_document_url(candidate.url):
            resolution_status = "direct_document"
        else:
            resolution_status = "unresolved"
            if candidate.url not in self.report.unresolved_document_urls:
                self.report.unresolved_document_urls.append(candidate.url)

        reported = ReportedCandidate(
            url=candidate.url,
            source_urls=[candidate.source_url],
            link_text=link_text,
            content_type=candidate.content_type,
            filename=candidate.filename,
            classification=status.value,
            resolution_status=resolution_status,
            is_direct_pdf=is_pdf_url(candidate.url),
        )
        self._candidate_index[normalized] = reported
        self.report.document_candidates.append(reported)

        if status == ClassificationStatus.RELEVANT:
            self.report.relevant_candidates.append(reported)
        elif status == ClassificationStatus.EXCLUDED:
            self.report.excluded_candidates.append(reported)
        else:
            self.report.review_candidates.append(reported)

    def _record_duplicate(self, url: str) -> None:
        normalized = normalize_url(url)
        if normalized not in self.report.duplicate_urls:
            self.report.duplicate_urls.append(normalized)

    def _record_robots_blocked(self, url: str) -> None:
        normalized = normalize_url(url)
        if normalized not in self.report.robots_blocked_urls:
            self.report.robots_blocked_urls.append(normalized)


def run_discovery(
    profile: SourceProfile,
    classifier: TriStateClassifier,
    *,
    max_pages: int = 100,
) -> DiscoveryReport:
    """Run a discovery-only crawl and return a structured report."""
    report = DiscoveryReport(source_name=profile.name)
    robots_checker = RobotsChecker()
    settings = build_scrapy_settings(profile)
    settings["USER_AGENT"] = USER_AGENT
    settings["CLOSESPIDER_PAGECOUNT"] = max_pages
    process = CrawlerProcess(settings=settings)
    process.crawl(
        DiscoverySpider,
        profile=profile,
        classifier=classifier,
        report=report,
        robots_checker=robots_checker,
        max_pages=max_pages,
    )
    process.start()
    return report
