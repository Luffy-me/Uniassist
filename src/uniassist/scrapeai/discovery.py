"""Link and document candidate discovery utilities."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import parse_qsl, urljoin, urlparse, urlunparse

from uniassist.scrapeai.models import DocumentCandidate, LinkCandidate

DOCUMENT_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
}

EXTENSION_TO_CONTENT_TYPE = DOCUMENT_EXTENSIONS


class _LinkExtractor(HTMLParser):
    """Collect anchor href values from HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = ""
        for key, value in attrs:
            if key == "href" and value:
                href = value.strip()
                break
        if href:
            self.links.append((href, ""))

    def handle_data(self, data: str) -> None:
        if self.links and not self.links[-1][1]:
            text = data.strip()
            if text:
                href, _ = self.links[-1]
                self.links[-1] = (href, text)


def normalize_url(url: str) -> str:
    """Normalize a URL for consistent comparison and deduplication."""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    query = urlencode_sorted(parse_qsl(parsed.query, keep_blank_values=True))
    return urlunparse((scheme, netloc, path, "", query, ""))


def urlencode_sorted(pairs: list[tuple[str, str]]) -> str:
    """Encode query parameters in sorted order for stable URLs."""
    if not pairs:
        return ""
    from urllib.parse import urlencode

    return urlencode(sorted(pairs))


def is_duplicate_url(url: str, seen: set[str]) -> bool:
    """Return True if the normalized *url* is already in *seen*."""
    normalized = normalize_url(url)
    return normalized in seen


def register_url(url: str, seen: set[str]) -> str:
    """Normalize *url*, add it to *seen*, and return the normalized form."""
    normalized = normalize_url(url)
    seen.add(normalized)
    return normalized


def extract_links(html: str, base_url: str) -> list[LinkCandidate]:
    """Extract hyperlinks from HTML and resolve them against *base_url*."""
    parser = _LinkExtractor()
    parser.feed(html)
    candidates: list[LinkCandidate] = []
    for href, text in parser.links:
        absolute = urljoin(base_url, href)
        if absolute.startswith(("http://", "https://")):
            candidates.append(
                LinkCandidate(url=absolute, source_url=base_url, text=text)
            )
    return candidates


def extension_for_url(url: str) -> str | None:
    """Return the lowercase file extension for *url*, if any."""
    path = urlparse(url).path
    dot = path.rfind(".")
    if dot == -1:
        return None
    return path[dot:].lower()


def detect_content_type_from_url(url: str) -> str | None:
    """Guess a MIME type from the URL path extension."""
    extension = extension_for_url(url)
    if extension is None:
        return None
    return EXTENSION_TO_CONTENT_TYPE.get(extension)


def is_pdf_url(url: str) -> bool:
    """Return True when *url* appears to reference a PDF."""
    return extension_for_url(url) == ".pdf"


def is_document_url(url: str) -> bool:
    """Return True when *url* appears to reference a supported document."""
    extension = extension_for_url(url)
    return extension in DOCUMENT_EXTENSIONS


def filename_from_url(url: str) -> str | None:
    """Extract a filename from the URL path, if present."""
    path = urlparse(url).path
    if not path or path.endswith("/"):
        return None
    name = path.rsplit("/", 1)[-1]
    return name or None


def detect_content_type(
    url: str,
    header_value: str | None = None,
) -> str | None:
    """Detect content type from an HTTP header or URL extension."""
    if header_value:
        content_type = header_value.split(";", 1)[0].strip().lower()
        if content_type:
            return content_type
    return detect_content_type_from_url(url)


def identify_document_candidates(
    links: list[LinkCandidate],
    allowed_content_types: list[str],
) -> list[DocumentCandidate]:
    """Filter link candidates down to potential document downloads."""
    allowed = {item.lower() for item in allowed_content_types}
    documents: list[DocumentCandidate] = []
    for link in links:
        content_type = detect_content_type_from_url(link.url)
        if content_type is None or content_type not in allowed:
            continue
        documents.append(
            DocumentCandidate(
                url=normalize_url(link.url),
                source_url=link.source_url,
                content_type=content_type,
                filename=filename_from_url(link.url),
            )
        )
    return documents


def create_document_candidate(
    url: str,
    source_url: str,
    content_type: str | None = None,
) -> DocumentCandidate:
    """Build a :class:`DocumentCandidate` with normalized fields."""
    resolved_type = content_type or detect_content_type_from_url(url)
    return DocumentCandidate(
        url=normalize_url(url),
        source_url=source_url,
        content_type=resolved_type,
        filename=filename_from_url(url),
    )
