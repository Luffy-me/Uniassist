"""Optional live Telegram Bot API integration tests."""

from __future__ import annotations

import json
import os
import urllib.request

import pytest


def _integration_enabled() -> bool:
    return os.environ.get("UNIASSIST_RUN_TELEGRAM_INTEGRATION") == "1"


@pytest.mark.asyncio
async def test_optional_telegram_get_me() -> None:
    if not _integration_enabled():
        pytest.skip("Telegram integration disabled")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        pytest.skip("TELEGRAM_BOT_TOKEN not set")

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/getMe"
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    assert payload["ok"] is True
    assert payload["result"]["is_bot"] is True
    assert "TELEGRAM_BOT_TOKEN" not in json.dumps(payload)
