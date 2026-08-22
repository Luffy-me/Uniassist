"""ScrapeAI — reusable data acquisition engine."""

from uniassist.scrapeai.classifier import (
    ClassificationRule,
    Classifier,
    RuleBasedClassifier,
    default_classifier,
)
from uniassist.scrapeai.config import DEFAULT_CONTENT_TYPES, SourceProfile
from uniassist.scrapeai.crawler import (
    ScrapeAISpider,
    build_scrapy_settings,
    run_crawler,
)
from uniassist.scrapeai.discovery import (
    create_document_candidate,
    detect_content_type,
    extract_links,
    identify_document_candidates,
    is_document_url,
    is_pdf_url,
    normalize_url,
)
from uniassist.scrapeai.downloader import DocumentDownloader
from uniassist.scrapeai.hashing import sha256_hex
from uniassist.scrapeai.models import (
    DocumentCandidate,
    DocumentMetadata,
    DownloadResult,
    LinkCandidate,
    Source,
)
from uniassist.scrapeai.storage import DocumentStorage

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
