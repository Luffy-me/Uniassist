"""Generic source configuration models for ScrapeAI."""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_CONTENT_TYPES: list[str] = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]


@dataclass(frozen=True)
class SourceProfile:
    """Configuration that describes how to crawl a data source.

    This model is intentionally generic — no source-specific values belong here.
    """

    name: str
    seed_urls: list[str]
    allowed_domains: list[str]
    respect_robots: bool = True
    allowed_content_types: list[str] = field(
        default_factory=lambda: list(DEFAULT_CONTENT_TYPES)
    )
    request_delay: float = 1.0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if not self.seed_urls:
            raise ValueError("seed_urls must contain at least one URL")
        if not self.allowed_domains:
            raise ValueError("allowed_domains must contain at least one domain")
        if self.request_delay < 0:
            raise ValueError("request_delay must be zero or positive")
