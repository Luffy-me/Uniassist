"""Generic document relevance classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from uniassist.scrapeai.discovery import detect_content_type_from_url, extension_for_url
from uniassist.scrapeai.models import DocumentCandidate


class ClassificationStatus(StrEnum):
    """Tri-state relevance outcome for a document candidate."""

    RELEVANT = "relevant"
    EXCLUDED = "excluded"
    REVIEW = "review"


class Classifier(Protocol):
    """Classify whether a document candidate is relevant."""

    def is_relevant(self, candidate: DocumentCandidate) -> bool:
        """Return True when the candidate should be downloaded."""


class TriStateClassifier(Protocol):
    """Classify a document candidate into relevant, excluded, or review."""

    def classify(
        self,
        candidate: DocumentCandidate,
        *,
        link_text: str = "",
    ) -> ClassificationStatus:
        """Return the tri-state classification for *candidate*."""


@dataclass(frozen=True)
class ClassificationRule:
    """A single configurable relevance rule."""

    extensions: set[str] = field(default_factory=set)
    path_contains: list[str] = field(default_factory=list)
    content_types: set[str] = field(default_factory=set)

    def matches(self, candidate: DocumentCandidate) -> bool:
        extension = extension_for_url(candidate.url) or ""
        content_type = (
            candidate.content_type or detect_content_type_from_url(candidate.url) or ""
        ).lower()
        path = candidate.url.lower()

        if self.extensions and extension in self.extensions:
            return True
        if self.content_types and content_type in self.content_types:
            return True
        if self.path_contains and any(token in path for token in self.path_contains):
            return True
        return False


class RuleBasedClassifier:
    """Classify candidates using one or more :class:`ClassificationRule` objects."""

    def __init__(self, rules: list[ClassificationRule]) -> None:
        if not rules:
            raise ValueError("at least one classification rule is required")
        self._rules = rules

    def is_relevant(self, candidate: DocumentCandidate) -> bool:
        return any(rule.matches(candidate) for rule in self._rules)


def default_classifier(allowed_content_types: list[str]) -> RuleBasedClassifier:
    """Build a classifier that accepts the configured content types."""
    extensions = {
        extension
        for extension, content_type in _CONTENT_TYPE_EXTENSIONS.items()
        if content_type in {item.lower() for item in allowed_content_types}
    }
    return RuleBasedClassifier(
        rules=[
            ClassificationRule(
                extensions=extensions,
                content_types={item.lower() for item in allowed_content_types},
            )
        ]
    )


@dataclass(frozen=True)
class KeywordClassificationConfig:
    """Keyword rules supplied by a source connector configuration."""

    inclusion_keywords: list[str] = field(default_factory=list)
    exclusion_keywords: list[str] = field(default_factory=list)


class KeywordClassifier:
    """Classify candidates using configurable inclusion and exclusion keywords."""

    def __init__(
        self,
        config: KeywordClassificationConfig,
        allowed_content_types: list[str],
    ) -> None:
        self._inclusion = [item.lower() for item in config.inclusion_keywords]
        self._exclusion = [item.lower() for item in config.exclusion_keywords]
        self._allowed_types = {item.lower() for item in allowed_content_types}

    def classify(
        self,
        candidate: DocumentCandidate,
        *,
        link_text: str = "",
    ) -> ClassificationStatus:
        searchable = self._search_text(candidate, link_text)

        for keyword in self._exclusion:
            if keyword in searchable:
                return ClassificationStatus.EXCLUDED

        for keyword in self._inclusion:
            if keyword in searchable:
                return ClassificationStatus.RELEVANT

        content_type = (
            candidate.content_type or detect_content_type_from_url(candidate.url) or ""
        ).lower()
        if content_type in self._allowed_types:
            return ClassificationStatus.REVIEW

        return ClassificationStatus.REVIEW

    def is_relevant(self, candidate: DocumentCandidate) -> bool:
        return self.classify(candidate) == ClassificationStatus.RELEVANT

    def _search_text(self, candidate: DocumentCandidate, link_text: str) -> str:
        parts = [
            candidate.url,
            candidate.filename or "",
            link_text,
        ]
        return " ".join(parts).lower()


_CONTENT_TYPE_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
}
