"""Command-line interface for grounded answers."""

from __future__ import annotations

import argparse
import os

from uniassist.ai.models import RefusalAnswer, VerifiedAnswer
from uniassist.ai.pipeline import AnswerPipeline
from uniassist.ai.providers.mock import MockLLMProvider
from uniassist.ai.providers.nvidia import NVIDIAProvider
from uniassist.ai.providers.nvidia_config import is_hosted_base_url, resolve_base_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="UniAssist grounded answer CLI (Phase 6)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask = subparsers.add_parser("ask", help="Ask a grounded question")
    ask.add_argument("question", help="Student question")
    ask.add_argument(
        "--mock",
        action="store_true",
        help="Use MockLLMProvider instead of NVIDIA",
    )
    ask.add_argument(
        "--provider-verify",
        action="store_true",
        help="Also run provider-side verification when using NVIDIA",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ask":
        provider = _resolve_provider(use_mock=args.mock)
        pipeline = AnswerPipeline.default(
            provider=provider,
            use_nvidia_semantic_verifier=args.provider_verify,
        )
        result = pipeline.ask(args.question)
        _print_result(result)
        if isinstance(result, RefusalAnswer):
            raise SystemExit(1)


def _resolve_provider(*, use_mock: bool):
    if use_mock:
        return MockLLMProvider()
    if os.environ.get("UNIASSIST_AI_USE_MOCK", "").strip() == "1":
        return MockLLMProvider()
    base_url = resolve_base_url()
    has_key = bool(os.environ.get("NVIDIA_API_KEY", "").strip())
    if has_key or not is_hosted_base_url(base_url):
        return NVIDIAProvider()
    raise SystemExit(
        "NVIDIA is not configured. Set NVIDIA_API_KEY for hosted NVIDIA, "
        "start local NVIDIA NIM, or pass --mock."
    )


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
