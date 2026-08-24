"""Ensure Appwrite Cloud schema is ready for UniAssist."""

from __future__ import annotations

import argparse
import json

from uniassist.persistence.appwrite_client import build_appwrite_clients
from uniassist.persistence.appwrite_schema import ensure_schema
from uniassist.persistence.config import AppwriteConfig


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ensure UniAssist Appwrite collection schema exists"
    )
    parser.parse_args()
    config = AppwriteConfig.from_env()
    config.validate_for_production()
    clients = build_appwrite_clients(config)
    report = ensure_schema(clients, config)
    print(
        json.dumps(
            {
                "created": report.created,
                "existing": report.existing,
                "failed": report.failed,
            },
            indent=2,
        )
    )
    if report.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
