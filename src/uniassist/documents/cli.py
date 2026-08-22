"""Command-line interface for document corpus administration."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from uniassist.documents.ingestion import DocumentIngestionService, IngestRequest
from uniassist.documents.models import SourceType


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="UniAssist document corpus administration (interim CLI)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    upload = subparsers.add_parser("upload", help="Upload a document into the corpus")
    upload.add_argument("file", type=Path, help="Path to the document file")
    upload.add_argument("--title", required=True, help="Document title")
    upload.add_argument("--source", required=True, help="Provenance source label")
    upload.add_argument("--source-url", default=None, help="Optional source URL")
    upload.add_argument(
        "--effective-date",
        type=date.fromisoformat,
        default=None,
        help="Effective date (YYYY-MM-DD)",
    )
    upload.add_argument("--version", default=None, help="Document version label")
    upload.add_argument("--notes", default=None, help="Optional admin notes")

    subparsers.add_parser("list", help="List documents in the corpus")

    show = subparsers.add_parser("show", help="Show one document by ID")
    show.add_argument("document_id", help="Document UUID")

    activate = subparsers.add_parser(
        "activate",
        help="Explicitly verify and activate a draft document",
    )
    activate.add_argument("document_id", help="Document UUID")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    service = DocumentIngestionService.default()

    if args.command == "upload":
        result = service.ingest_file(
            args.file,
            IngestRequest(
                title=args.title,
                source=args.source,
                source_type=SourceType.ADMIN_UPLOAD,
                source_url=args.source_url,
                effective_date=args.effective_date,
                version=args.version,
                notes=args.notes,
            ),
        )
        print(json.dumps(result.record.to_dict(), ensure_ascii=False, indent=2))
        if result.duplicate:
            print("duplicate: existing content returned")
        return

    if args.command == "list":
        records = service.list_documents()
        for record in records:
            print(
                f"{record.document_id}\t{record.status.value}\t"
                f"{record.verification_state.value}\t{record.title}"
            )
        return

    if args.command == "show":
        record = service.get_document(args.document_id)
        if record is None:
            raise SystemExit(f"document not found: {args.document_id}")
        print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
        return

    if args.command == "activate":
        record = service.activate(args.document_id)
        print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
