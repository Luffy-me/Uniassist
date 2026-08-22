"""Tests for the SUSU official regulations connector."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from urllib.robotparser import RobotFileParser

from scrapy.http import HtmlResponse

from uniassist.scrapeai.classifier import ClassificationStatus
from uniassist.scrapeai.discovery import (
    extract_links,
    identify_document_candidates,
    is_pdf_url,
)
from uniassist.scrapeai.discovery_crawler import DiscoverySpider, RobotsChecker
from uniassist.scrapeai.discovery_report import DiscoveryReport
from uniassist.scrapeai.models import DocumentCandidate
from uniassist.scrapeai.sources.susu.official_regulations import (
    build_classifier,
    build_source_profile,
    load_yaml_config,
)

from .conftest import SAMPLE_SUSU_HTML


def test_source_profile_loads_correctly(susu_config: dict) -> None:
    profile = build_source_profile(susu_config)
    assert profile.name == "susu-official-regulations"
    assert profile.respect_robots is True
    assert profile.request_delay == 10.0


def test_allowed_susu_domains_are_correct(susu_config: dict) -> None:
    profile = build_source_profile(susu_config)
    assert profile.allowed_domains == ["susu.ru"]


def test_seed_urls_load_from_yaml(susu_config: dict) -> None:
    seeds = susu_config["seed_urls"]
    assert "https://www.susu.ru/ru/university/official/documents" in seeds
    assert "https://k.susu.ru/index.php/lokalnye-normativnye-akty" in seeds


def test_inclusion_rules_mark_student_documents_relevant(susu_config: dict) -> None:
    classifier = build_classifier(susu_config)
    candidate = DocumentCandidate(
        url="https://www.susu.ru/files/transfer.pdf",
        source_url="https://www.susu.ru/ru/university/official/documents",
        content_type="application/pdf",
        filename="transfer.pdf",
    )
    assert (
        classifier.classify(
            candidate,
            link_text="Положение о переводе обучающихся",
        )
        == ClassificationStatus.RELEVANT
    )


def test_exclusion_rules_mark_staff_documents_excluded(susu_config: dict) -> None:
    classifier = build_classifier(susu_config)
    candidate = DocumentCandidate(
        url="https://www.susu.ru/files/charter.pdf",
        source_url="https://www.susu.ru/ru/university/official/documents",
        content_type="application/pdf",
        filename="charter.pdf",
    )
    assert (
        classifier.classify(candidate, link_text="Устав университета")
        == ClassificationStatus.EXCLUDED
    )


def test_uncertain_documents_are_marked_for_review(susu_config: dict) -> None:
    classifier = build_classifier(susu_config)
    candidate = DocumentCandidate(
        url="https://www.susu.ru/files/misc.pdf",
        source_url="https://www.susu.ru/ru/university/official/documents",
        content_type="application/pdf",
        filename="misc.pdf",
    )
    assert (
        classifier.classify(candidate, link_text="Документ без явной тематики")
        == ClassificationStatus.REVIEW
    )


def test_susu_pdf_links_are_detected() -> None:
    links = extract_links(
        SAMPLE_SUSU_HTML,
        "https://www.susu.ru/ru/university/official/documents",
    )
    documents = identify_document_candidates(links, ["application/pdf"])
    pdf_urls = {doc.url for doc in documents}
    assert "https://www.susu.ru/sites/default/files/rules/students.pdf" in pdf_urls
    assert "https://k.susu.ru/_olan/_docs/pol_tek_kontr_bsm.pdf" in pdf_urls
    assert all(is_pdf_url(url) for url in pdf_urls)


def test_duplicate_links_are_removed_in_discovery_report(susu_config: dict) -> None:
    profile = build_source_profile(susu_config)
    classifier = build_classifier(susu_config)
    report = DiscoveryReport(source_name=profile.name)
    spider = DiscoverySpider(
        profile=profile,
        classifier=classifier,
        report=report,
        robots_checker=RobotsChecker(),
        max_pages=10,
    )
    response = HtmlResponse(
        url="https://www.susu.ru/ru/university/official/documents",
        body=SAMPLE_SUSU_HTML.encode(),
        encoding="utf-8",
    )
    list(spider.parse_page(response))
    list(spider.parse_page(response))

    assert len(report.duplicate_urls) > 0


def test_robots_blocked_documents_are_recorded(susu_config: dict) -> None:
    def _fake_robots_read(self: RobotFileParser) -> None:
        self.parse(
            [
                "User-agent: *",
                "Disallow: /admin/",
                "",
            ]
        )

    with patch.object(RobotFileParser, "read", _fake_robots_read):
        checker = RobotsChecker()
        assert checker.is_allowed("https://www.susu.ru/admin/secret.pdf", True) is False

    profile = build_source_profile(susu_config)
    classifier = build_classifier(susu_config)
    report = DiscoveryReport(source_name=profile.name)
    spider = DiscoverySpider(
        profile=profile,
        classifier=classifier,
        report=report,
        robots_checker=RobotsChecker(),
        max_pages=10,
    )
    spider._record_robots_blocked("https://www.susu.ru/admin/secret.pdf")
    assert "https://www.susu.ru/admin/secret.pdf" in report.robots_blocked_urls


def test_dry_run_report_schema(susu_config: dict) -> None:
    profile = build_source_profile(susu_config)
    classifier = build_classifier(susu_config)
    report = DiscoveryReport(source_name=profile.name)
    spider = DiscoverySpider(
        profile=profile,
        classifier=classifier,
        report=report,
        robots_checker=RobotsChecker(),
        max_pages=10,
    )
    response = HtmlResponse(
        url="https://www.susu.ru/ru/university/official/documents",
        body=SAMPLE_SUSU_HTML.encode(),
        encoding="utf-8",
    )
    list(spider.parse_page(response))

    payload = report.to_dict()
    assert payload["source_name"] == "susu-official-regulations"
    assert "pages_visited" in payload
    assert "links_discovered" in payload
    assert "document_candidates" in payload
    assert "relevant_candidates" in payload
    assert "excluded_candidates" in payload
    assert "review_candidates" in payload
    assert "direct_pdf_urls" in payload
    assert "unresolved_document_urls" in payload
    assert "robots_blocked_urls" in payload
    assert "duplicate_urls" in payload
    assert "summary" in payload
    assert payload["summary"]["relevant_candidates"] >= 1
    assert payload["summary"]["excluded_candidates"] >= 1
    assert payload["summary"]["review_candidates"] >= 1


def test_yaml_config_file_exists(config_path: Path) -> None:
    assert config_path.exists()
    config = load_yaml_config(config_path)
    assert "inclusion_keywords" in config
    assert "exclusion_keywords" in config
