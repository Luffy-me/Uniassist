"""Import a curated set of official SUSU international-student web pages."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.request import Request, urlopen

from lxml import html

from uniassist.documents.ingestion import DocumentIngestionService, IngestRequest
from uniassist.processing.models import ProcessingStatus
from uniassist.processing.service import DocumentProcessingService
from uniassist.rag.indexing import IndexingService

PAGES = (
    (
        "Programmes for International Students",
        "https://www.susu.ru/en/programmes-international-students",
    ),
    (
        "English-Taught Programmes",
        "https://www.susu.ru/en/education/english-taught-programmes",
    ),
    ("How to Apply to SUSU", "https://www.susu.ru/en/webform/apply-now"),
    (
        "Government Scholarship for International Students",
        "https://www.susu.ru/en/programs/education-programs-foreign-students/government-scholarship",
    ),
    (
        "Degree Recognition",
        "https://www.susu.ru/en/international-relations-0/international-office/degree-recognition/en",
    ),
    (
        "Association of International Students and Alumni",
        "https://www.susu.ru/en/campus-life/association-international-students-and-alumni",
    ),
)


def _snapshot(title: str, url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "UniAssist/1.0"})
    with urlopen(request, timeout=30) as response:  # noqa: S310
        page = html.fromstring(response.read())
    body = page.xpath('//*[contains(@class, "field-name-body")]')
    if not body:
        raise RuntimeError(f"No article body found: {url}")
    text = "\n".join(
        item.strip() for item in body[0].xpath(".//text()") if item.strip()
    )
    snapshot = (
        f"{title}\n\nOfficial source URL: {url}\n"
        f"Retrieved: {datetime.now(UTC).date()}\n\n{text}\n"
    )
    return snapshot.encode()


def main() -> None:
    ingestion = DocumentIngestionService.default()
    processing = DocumentProcessingService.default()
    indexing = IndexingService.default()
    for number, (title, url) in enumerate(PAGES, 1):
        result = ingestion.ingest_bytes(
            filename=f"susu_international_{number}.txt",
            content=_snapshot(title, url),
            request=IngestRequest(
                title=title,
                source="South Ural State University official website",
                source_url=url,
                notes=(
                    "Admin-curated official website snapshot for international "
                    "students."
                ),
            ),
        )
        if result.duplicate:
            print(f"duplicate: {title}")
            continue
        ingestion.activate(result.record.document_id)
        processed = processing.process_document(result.record.document_id)
        if processed.status != ProcessingStatus.COMPLETED:
            raise RuntimeError(f"Processing failed: {title}: {processed.error}")
        indexed = indexing.index_document(result.record.document_id)
        print(f"indexed: {title} ({indexed.chunks_indexed} chunks)")


if __name__ == "__main__":
    main()
