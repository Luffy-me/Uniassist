"""Telegram student bot configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

TELEGRAM_MAX_MESSAGE_LENGTH_DEFAULT = 4096
TELEGRAM_RATE_LIMIT_DEFAULT = 10
TELEGRAM_TIMEOUT_DEFAULT = 60.0


class TelegramConfigError(ValueError):
    """Raised when Telegram bot configuration is invalid."""


@dataclass(frozen=True)
class TelegramConfig:
    """Runtime configuration for the Telegram bot."""

    bot_token: str
    api_url: str
    rate_limit_per_minute: int = TELEGRAM_RATE_LIMIT_DEFAULT
    request_timeout_seconds: float = TELEGRAM_TIMEOUT_DEFAULT
    max_message_length: int = TELEGRAM_MAX_MESSAGE_LENGTH_DEFAULT

    @classmethod
    def from_env(cls) -> TelegramConfig:
        """Load configuration from environment variables."""
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise TelegramConfigError(
                "TELEGRAM_BOT_TOKEN is not set. Add it to your environment."
            )
        api_url = os.environ.get("UNIASSIST_API_URL", "").strip().rstrip("/")
        if not api_url:
            raise TelegramConfigError(
                "UNIASSIST_API_URL is not set. Example: http://127.0.0.1:8000"
            )
        rate_limit = int(
            os.environ.get(
                "TELEGRAM_RATE_LIMIT_PER_MINUTE",
                str(TELEGRAM_RATE_LIMIT_DEFAULT),
            )
        )
        timeout = float(
            os.environ.get(
                "TELEGRAM_REQUEST_TIMEOUT_SECONDS",
                str(TELEGRAM_TIMEOUT_DEFAULT),
            )
        )
        max_length = int(
            os.environ.get(
                "TELEGRAM_MAX_MESSAGE_LENGTH",
                str(TELEGRAM_MAX_MESSAGE_LENGTH_DEFAULT),
            )
        )
        if rate_limit <= 0:
            raise TelegramConfigError("TELEGRAM_RATE_LIMIT_PER_MINUTE must be positive")
        if timeout <= 0:
            raise TelegramConfigError(
                "TELEGRAM_REQUEST_TIMEOUT_SECONDS must be positive"
            )
        if max_length <= 0:
            raise TelegramConfigError("TELEGRAM_MAX_MESSAGE_LENGTH must be positive")
        return cls(
            bot_token=token,
            api_url=api_url,
            rate_limit_per_minute=rate_limit,
            request_timeout_seconds=timeout,
            max_message_length=max_length,
        )
