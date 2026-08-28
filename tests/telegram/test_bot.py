"""Tests for Telegram bot factory and import safety."""

from __future__ import annotations

import importlib

from uniassist.telegram.bot import create_bot
from uniassist.telegram.config import TelegramConfig


def test_package_import_without_token() -> None:
    importlib.import_module("uniassist.telegram")
    importlib.import_module("uniassist.telegram.handlers")


def test_create_bot_registers_handlers(telegram_config: TelegramConfig) -> None:
    application = create_bot(telegram_config)
    assert application.handlers
    assert application.error_handlers
    assert application.bot_data["services"] is not None


def test_create_bot_configures_resilient_telegram_timeouts(
    telegram_config: TelegramConfig,
) -> None:
    application = create_bot(telegram_config)
    polling_request, normal_request = application.bot._request  # noqa: SLF001
    assert normal_request._client.timeout.connect == 12.0  # noqa: SLF001
    assert normal_request._client.timeout.read == 12.0  # noqa: SLF001
    assert polling_request._client.timeout.connect == 12.0  # noqa: SLF001
    assert polling_request._client.timeout.read == 20.0  # noqa: SLF001
