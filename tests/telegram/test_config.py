"""Tests for Telegram configuration."""

from __future__ import annotations

import pytest

from uniassist.telegram.config import TelegramConfig, TelegramConfigError


def test_config_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("UNIASSIST_API_URL", "http://127.0.0.1:8000/")
    config = TelegramConfig.from_env()
    assert config.bot_token == "secret-token"
    assert config.api_url == "http://127.0.0.1:8000"
    assert config.rate_limit_per_minute == 10


def test_missing_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("UNIASSIST_API_URL", "http://127.0.0.1:8000")
    with pytest.raises(TelegramConfigError, match="TELEGRAM_BOT_TOKEN"):
        TelegramConfig.from_env()


def test_missing_api_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.delenv("UNIASSIST_API_URL", raising=False)
    with pytest.raises(TelegramConfigError, match="UNIASSIST_API_URL"):
        TelegramConfig.from_env()
