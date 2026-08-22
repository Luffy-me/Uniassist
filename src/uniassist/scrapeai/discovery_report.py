"""Structured discovery report models for dry-run crawling."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ReportedCandidate:
    """A document candidate included in a discovery report."""

    url: str
    source_urls: list[str]
    link_text: str = ""
    content_type: str | None = None
    filename: str | None = None
    classification: str = "review"
    resolution_status: str = "discovered"
    is_direct_pdf: bool = False


@dataclass
class DiscoveryReport:
    """Aggregated output from a discovery-only crawl."""

    source_name: str
    pages_visited: list[str] = field(default_factory=list)
    links_discovered: list[dict[str, str]] = field(default_factory=list)
    document_candidates: list[ReportedCandidate] = field(default_factory=list)
    relevant_candidates: list[ReportedCandidate] = field(default_factory=list)
    excluded_candidates: list[ReportedCandidate] = field(default_factory=list)
    review_candidates: list[ReportedCandidate] = field(default_factory=list)
    direct_pdf_urls: list[str] = field(default_factory=list)
    unresolved_document_urls: list[str] = field(default_factory=list)
    robots_blocked_urls: list[str] = field(default_factory=list)
    duplicate_urls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "pages_visited": self.pages_visited,
            "links_discovered": self.links_discovered,
            "document_candidates": [asdict(item) for item in self.document_candidates],
            "relevant_candidates": [asdict(item) for item in self.relevant_candidates],
            "excluded_candidates": [asdict(item) for item in self.excluded_candidates],
            "review_candidates": [asdict(item) for item in self.review_candidates],
            "direct_pdf_urls": self.direct_pdf_urls,
            "unresolved_document_urls": self.unresolved_document_urls,
            "robots_blocked_urls": self.robots_blocked_urls,
            "duplicate_urls": self.duplicate_urls,
            "summary": {
                "pages_visited": len(self.pages_visited),
                "links_discovered": len(self.links_discovered),
                "document_candidates": len(self.document_candidates),
                "relevant_candidates": len(self.relevant_candidates),
                "excluded_candidates": len(self.excluded_candidates),
                "review_candidates": len(self.review_candidates),
                "direct_pdf_urls": len(self.direct_pdf_urls),
                "unresolved_document_urls": len(self.unresolved_document_urls),
                "robots_blocked_urls": len(self.robots_blocked_urls),
                "duplicate_urls": len(self.duplicate_urls),
            },
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
