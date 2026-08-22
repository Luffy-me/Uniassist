"""Command-line interface for document processing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from uniassist.processing.service import DocumentProcessingService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="UniAssist document processing (Phase 4 CLI)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    process = subparsers.add_parser(
        "process",
        help="Process an ACTIVE + VERIFIED document",
    )
    process.add_argument("document_id", help="Document UUID")

    show = subparsers.add_parser(
        "show",
        help="Show processing result for a document",
    )
    show.add_argument("document_id", help="Document UUID")

    subparsers.add_parser("list", help="List processing results")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    service = DocumentProcessingService.default()

    if args.command == "process":
        result = service.process_document(args.document_id)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        if result.status.value in {"failed", "unsupported"}:
            raise SystemExit(1)
        return

    if args.command == "show":
        result = service.get_result(args.document_id)
        if result is None:
            raise SystemExit(f"no processing result for: {args.document_id}")
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        normalized_path = (
            Path("data")
            / "processed"
            / args.document_id
            / (result.source_sha256 or "")
            / "normalized.json"
        )
        if normalized_path.exists():
            print()
            print(normalized_path.read_text(encoding="utf-8"))
        return

    if args.command == "list":
        for result in service.list_results():
            print(
                f"{result.document_id}\t{result.status.value}\t"
                f"{result.processor}\t{result.output_path or '-'}"
            )


if __name__ == "__main__":
    main()
