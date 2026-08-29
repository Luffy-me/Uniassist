"""ScrapeAI — reusable data acquisition engine."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "DEFAULT_CONTENT_TYPES",
    "ClassificationRule",
    "Classifier",
    "DocumentCandidate",
    "DocumentDownloader",
    "DocumentMetadata",
    "DocumentStorage",
    "DownloadResult",
    "LinkCandidate",
    "RuleBasedClassifier",
    "ScrapeAISpider",
    "Source",
    "SourceProfile",
    "build_scrapy_settings",
    "create_document_candidate",
    "default_classifier",
    "detect_content_type",
    "extract_links",
    "identify_document_candidates",
    "is_document_url",
    "is_pdf_url",
    "normalize_url",
    "run_crawler",
    "sha256_hex",
]

_MODULE_BY_NAME = {
    "ClassificationRule": "uniassist.scrapeai.classifier",
    "Classifier": "uniassist.scrapeai.classifier",
    "RuleBasedClassifier": "uniassist.scrapeai.classifier",
    "default_classifier": "uniassist.scrapeai.classifier",
    "DEFAULT_CONTENT_TYPES": "uniassist.scrapeai.config",
    "SourceProfile": "uniassist.scrapeai.config",
    "ScrapeAISpider": "uniassist.scrapeai.crawler",
    "build_scrapy_settings": "uniassist.scrapeai.crawler",
    "run_crawler": "uniassist.scrapeai.crawler",
    "create_document_candidate": "uniassist.scrapeai.discovery",
    "detect_content_type": "uniassist.scrapeai.discovery",
    "extract_links": "uniassist.scrapeai.discovery",
    "identify_document_candidates": "uniassist.scrapeai.discovery",
    "is_document_url": "uniassist.scrapeai.discovery",
    "is_pdf_url": "uniassist.scrapeai.discovery",
    "normalize_url": "uniassist.scrapeai.discovery",
    "DocumentDownloader": "uniassist.scrapeai.downloader",
    "sha256_hex": "uniassist.scrapeai.hashing",
    "DocumentCandidate": "uniassist.scrapeai.models",
    "DocumentMetadata": "uniassist.scrapeai.models",
    "DownloadResult": "uniassist.scrapeai.models",
    "LinkCandidate": "uniassist.scrapeai.models",
    "Source": "uniassist.scrapeai.models",
    "DocumentStorage": "uniassist.scrapeai.storage",
}


def __getattr__(name: str) -> Any:
    module_name = _MODULE_BY_NAME.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    return getattr(module, name)
