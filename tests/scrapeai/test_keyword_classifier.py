"""Tests for the generic keyword classifier."""

from __future__ import annotations

from uniassist.scrapeai.classifier import (
    ClassificationStatus,
    KeywordClassificationConfig,
    KeywordClassifier,
)
from uniassist.scrapeai.models import DocumentCandidate


def test_keyword_classifier_supports_review_status() -> None:
    classifier = KeywordClassifier(
        KeywordClassificationConfig(
            inclusion_keywords=["student"],
            exclusion_keywords=["staff"],
        ),
        allowed_content_types=["application/pdf"],
    )
    review_candidate = DocumentCandidate(
        url="https://example.org/files/unknown.pdf",
        source_url="https://example.org/",
        content_type="application/pdf",
    )
    assert classifier.classify(review_candidate) == ClassificationStatus.REVIEW
