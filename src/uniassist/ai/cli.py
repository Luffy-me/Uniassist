"""Command-line interface for grounded answers."""

from __future__ import annotations

import argparse
import os

from uniassist.ai.models import RefusalAnswer, VerifiedAnswer
from uniassist.ai.pipeline import AnswerPipeline
from uniassist.ai.providers.groq import GroqProvider
from uniassist.ai.providers.mock import MockLLMProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="UniAssist grounded answer CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask = subparsers.add_parser("ask", help="Ask a grounded question")
    ask.add_argument("question", help="Student question")
    ask.add_argument(
        "--mock",
        action="store_true",
        help="Use MockLLMProvider instead of Groq",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ask":
        provider = _resolve_provider(use_mock=args.mock)
        pipeline = AnswerPipeline.default(provider=provider)
        result = pipeline.ask(args.question)
        _print_result(result)
        if isinstance(result, RefusalAnswer):
            raise SystemExit(1)


def _resolve_provider(*, use_mock: bool):
    if use_mock:
        return MockLLMProvider()
    if os.environ.get("UNIASSIST_AI_USE_MOCK", "").strip() == "1":
        return MockLLMProvider()
    return GroqProvider()


def _print_result(result: VerifiedAnswer | RefusalAnswer) -> None:
    if isinstance(result, VerifiedAnswer):
        print("VERIFIED\n")
        print(result.answer_text)
        if result.citations:
            print("\nSources:")
            for citation in result.citations:
                print(f"- {citation.display_label()}")
        return

    print("NOT VERIFIED\n")
    print(result.message)
    if result.verification_result.reasoning_summary:
        print(f"\nReason: {result.verification_result.reasoning_summary}")


if __name__ == "__main__":
    main()
