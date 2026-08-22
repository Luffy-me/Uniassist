"""SUSU official regulations source connector."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from uniassist.scrapeai.classifier import KeywordClassificationConfig, KeywordClassifier
from uniassist.scrapeai.config import SourceProfile
from uniassist.scrapeai.discovery_crawler import run_discovery
from uniassist.scrapeai.discovery_report import DiscoveryReport

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[5]
    / "configs"
    / "susu"
    / "official_regulations.yaml"
)
DEFAULT_REPORT_PATH = (
    Path(__file__).resolve().parents[5]
    / "data"
    / "metadata"
    / "susu_official_regulations_dry_run.json"
)


def default_config_path() -> Path:
    """Return the default path to the SUSU official regulations YAML file."""
    return DEFAULT_CONFIG_PATH


def default_report_path() -> Path:
    """Return the default path for the dry-run JSON report."""
    return DEFAULT_REPORT_PATH


def load_yaml_config(path: Path | None = None) -> dict[str, Any]:
    """Load the SUSU official regulations YAML configuration."""
    config_path = path or default_config_path()
    with config_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"invalid config file: {config_path}")
    return data


def build_source_profile(config: dict[str, Any]) -> SourceProfile:
    """Build a generic :class:`SourceProfile` from SUSU YAML config."""
    return SourceProfile(
        name=str(config["name"]),
        seed_urls=list(config["seed_urls"]),
        allowed_domains=list(config["allowed_domains"]),
        respect_robots=bool(config.get("respect_robots", True)),
        allowed_content_types=list(config.get("allowed_content_types", [])),
        request_delay=float(config.get("request_delay", 1.0)),
    )


def build_classifier(config: dict[str, Any]) -> KeywordClassifier:
    """Build a keyword classifier from SUSU YAML config."""
    keyword_config = KeywordClassificationConfig(
        inclusion_keywords=list(config.get("inclusion_keywords", [])),
        exclusion_keywords=list(config.get("exclusion_keywords", [])),
    )
    return KeywordClassifier(
        keyword_config,
        allowed_content_types=list(config.get("allowed_content_types", [])),
    )


def run_dry_run(
    config_path: Path | None = None,
    report_path: Path | None = None,
) -> DiscoveryReport:
    """Discover and classify SUSU documents without downloading files."""
    config = load_yaml_config(config_path)
    profile = build_source_profile(config)
    classifier = build_classifier(config)
    max_pages = int(config.get("max_pages", 100))
    report = run_discovery(profile, classifier, max_pages=max_pages)
    output = report_path or default_report_path()
    report.save(output)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SUSU official regulations discovery for ScrapeAI",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover and classify documents without downloading files",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to official_regulations.yaml",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Path for the JSON dry-run report",
    )
    args = parser.parse_args()

    if not args.dry_run:
        parser.error("only --dry-run is supported in Phase 2")

    report = run_dry_run(config_path=args.config, report_path=args.report)
    summary = report.to_dict()["summary"]
    print(f"Dry-run complete. Report saved to {args.report or default_report_path()}")
    print(f"Relevant: {summary['relevant_candidates']}")
    print(f"Excluded: {summary['excluded_candidates']}")
    print(f"Review: {summary['review_candidates']}")
    print(f"Direct PDFs: {summary['direct_pdf_urls']}")
    print(f"Robots blocked: {summary['robots_blocked_urls']}")


if __name__ == "__main__":
    main()
