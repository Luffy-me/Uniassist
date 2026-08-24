"""Shared fixtures for live Appwrite integration tests."""

from __future__ import annotations

import os
import uuid

import pytest

from uniassist.persistence.appwrite_client import (
    AppwriteClients,
    build_appwrite_clients,
)
from uniassist.persistence.appwrite_schema import ensure_schema
from uniassist.persistence.config import AppwriteConfig


def require_appwrite_integration() -> AppwriteConfig:
    if os.environ.get("UNIASSIST_RUN_APPWRITE_INTEGRATION") != "1":
        pytest.skip("Set UNIASSIST_RUN_APPWRITE_INTEGRATION=1 to run Appwrite tests")
    config = AppwriteConfig.try_from_env()
    if config is None:
        pytest.skip("Appwrite credentials are not configured")
    return config


@pytest.fixture(scope="session")
def appwrite_config() -> AppwriteConfig:
    return require_appwrite_integration()


@pytest.fixture(scope="session")
def appwrite_clients(appwrite_config: AppwriteConfig) -> AppwriteClients:
    return build_appwrite_clients(appwrite_config)


@pytest.fixture(scope="session", autouse=True)
def appwrite_schema_ready(
    appwrite_clients: AppwriteClients,
    appwrite_config: AppwriteConfig,
):
    report = ensure_schema(appwrite_clients, appwrite_config)
    if report.failed:
        pytest.fail(
            "Appwrite schema setup failed for attributes: "
            + ", ".join(report.failed)
        )
    yield report


@pytest.fixture
def test_namespace() -> str:
    return f"integration-test-{uuid.uuid4().hex[:12]}"
