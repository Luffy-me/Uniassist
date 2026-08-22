"""Optional live Appwrite integration tests."""

from __future__ import annotations

import os

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.appwrite]


def _require_appwrite_integration() -> None:
    if os.environ.get("UNIASSIST_RUN_APPWRITE_INTEGRATION") != "1":
        pytest.skip("Set UNIASSIST_RUN_APPWRITE_INTEGRATION=1 to run Appwrite tests")
    from uniassist.persistence.config import AppwriteConfig

    if AppwriteConfig.try_from_env() is None:
        pytest.skip("Appwrite credentials are not configured")


def test_appwrite_configuration_is_present() -> None:
    _require_appwrite_integration()
    from uniassist.persistence.config import AppwriteConfig

    config = AppwriteConfig.from_env()
    summary = config.redacted_summary()
    assert summary["endpoint"]
    assert summary["api_key_configured"] == "yes"
