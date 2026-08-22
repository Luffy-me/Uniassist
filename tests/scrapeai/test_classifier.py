"""Tests for the rule-based classifier."""

from __future__ import annotations

from uniassist.scrapeai.classifier import ClassificationRule, RuleBasedClassifier
from uniassist.scrapeai.models import DocumentCandidate


def test_classifier_accepts_matching_extension() -> None:
    classifier = RuleBasedClassifier(
        rules=[ClassificationRule(extensions={".pdf"})]
    )
    candidate = DocumentCandidate(
        url="https://example.org/report.pdf",
        source_url="https://example.org/",
        content_type="application/pdf",
    )
    assert classifier.is_relevant(candidate) is True


def test_classifier_rejects_non_matching_candidate() -> None:
    classifier = RuleBasedClassifier(
        rules=[ClassificationRule(extensions={".pdf"})]
    )
    candidate = DocumentCandidate(
        url="https://example.org/page.html",
        source_url="https://example.org/",
    )
    assert classifier.is_relevant(candidate) is False


def test_classifier_honors_path_contains_rules() -> None:
    classifier = RuleBasedClassifier(
        rules=[ClassificationRule(path_contains=["/publications/"])]
    )
    candidate = DocumentCandidate(
        url="https://example.org/publications/paper.docx",
        source_url="https://example.org/",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert classifier.is_relevant(candidate) is True
