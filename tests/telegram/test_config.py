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
    assert config.network_timeout_seconds == 30.0
    assert config.poll_timeout_seconds == 30
    assert config.bootstrap_retries == 3


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("TELEGRAM_NETWORK_TIMEOUT_SECONDS", "0", "NETWORK_TIMEOUT"),
        ("TELEGRAM_POLL_TIMEOUT_SECONDS", "0", "POLL_TIMEOUT"),
        ("TELEGRAM_BOOTSTRAP_RETRIES", "-1", "BOOTSTRAP_RETRIES"),
    ],
)
def test_invalid_transport_settings_raise(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
    message: str,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("UNIASSIST_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv(name, value)
    with pytest.raises(TelegramConfigError, match=message):
        TelegramConfig.from_env()


def test_non_numeric_setting_raises_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("UNIASSIST_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("TELEGRAM_NETWORK_TIMEOUT_SECONDS", "slow")
    with pytest.raises(TelegramConfigError, match="valid numbers"):
        TelegramConfig.from_env()


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
