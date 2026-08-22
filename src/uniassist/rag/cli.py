"""Command-line interface for RAG indexing and retrieval."""

from __future__ import annotations

import argparse
import json

from uniassist.rag.indexing import IndexingService
from uniassist.rag.retrieval import Retriever


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="UniAssist RAG evidence retrieval (Phase 5/6.5 CLI)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    index = subparsers.add_parser("index", help="Index processed documents")
    index.add_argument(
        "document_id",
        nargs="?",
        default=None,
        help="Optional document UUID; index all eligible when omitted",
    )
    index.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild the full index from scratch before indexing",
    )

    subparsers.add_parser(
        "rebuild",
        help="Explicitly rebuild the entire vector index",
    )

    search = subparsers.add_parser("search", help="Search indexed evidence")
    search.add_argument("query", help="Search query")
    search.add_argument("--top-k", type=int, default=5, help="Number of results")
    search.add_argument(
        "--min-score",
        type=float,
        default=None,
        help="Optional minimum cosine similarity threshold",
    )

    subparsers.add_parser("stats", help="Show index statistics")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "index":
        service = IndexingService.default()
        if args.rebuild:
            report = service.rebuild_index()
            print(_format_rebuild_report(report))
            return
        if args.document_id:
            result = service.index_document(args.document_id)
            print(
                json.dumps(
                    result.__dict__,
                    default=str,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        results = service.index_all_eligible()
        print(
            json.dumps(
                [result.__dict__ for result in results],
                default=str,
                indent=2,
            )
        )
        return

    if args.command == "rebuild":
        service = IndexingService.default()
        report = service.rebuild_index()
        print(_format_rebuild_report(report))
        return

    if args.command == "search":
        retriever = Retriever.default()
        if args.min_score is not None:
            from uniassist.rag.retrieval import RetrievalConfig

            retriever = Retriever.default(
                config=RetrievalConfig(min_score=args.min_score),
            )
        results = retriever.retrieve(args.query, top_k=args.top_k)
        if not results:
            print("No results.")
            return
        for item in results:
            chunk = item.chunk
            preview = chunk.text.replace("\n", " ")
            if len(preview) > 160:
                preview = f"{preview[:157]}..."
            print(
                f"{item.rank}. score={item.similarity_score:.4f}\n"
                f"   Document: {chunk.title} ({chunk.document_id})\n"
                f"   Page: {chunk.page_number}\n"
                f"   Section: {chunk.section}\n"
                f"   Source: {chunk.source}\n"
                f"   {preview}\n"
            )
        return

    if args.command == "stats":
        service = IndexingService.default()
        stats = service.stats()
        print(json.dumps(stats.__dict__, ensure_ascii=False, indent=2))


def _format_rebuild_report(report) -> str:
    return (
        "Index rebuild complete\n"
        f"  documents indexed: {report.documents_indexed}\n"
        f"  chunks created: {report.chunks_created}\n"
        f"  embeddings generated: {report.embeddings_generated}\n"
        f"  embedding model: {report.embedding_model}\n"
        f"  vector dimension: {report.embedding_dimension}\n"
        f"  provider: {report.provider_name}\n"
        f"  duration: {report.duration_seconds:.2f}s"
    )


if __name__ == "__main__":
    main()
