"""Shared fixtures for Telegram bot tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Update

from uniassist.telegram.config import TelegramConfig
from uniassist.telegram.handlers import BotServices, build_services


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "metadata").mkdir(parents=True)
    (tmp_path / "data" / "processed").mkdir(parents=True)
    (tmp_path / "data" / "metadata" / "rag").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def telegram_config() -> TelegramConfig:
    return TelegramConfig(
        bot_token="test-token",
        api_url="http://127.0.0.1:8000",
        rate_limit_per_minute=3,
        request_timeout_seconds=5.0,
        max_message_length=500,
        network_timeout_seconds=12.0,
        poll_timeout_seconds=8,
        bootstrap_retries=2,
    )


@pytest.fixture
def bot_services(telegram_config: TelegramConfig) -> BotServices:
    services = build_services(telegram_config)
    services.rate_limiter.reset()
    services.session_store.clear()
    return services


def make_update(
    *,
    text: str | None = None,
    user_id: int = 42,
    chat_id: int = 100,
) -> Update:
    update = MagicMock(spec=Update)
    message = MagicMock()
    message.text = text
    message.reply_text = AsyncMock()
    user = MagicMock()
    user.id = user_id
    chat = MagicMock()
    chat.id = chat_id
    update.effective_message = message
    update.effective_user = user
    update.effective_chat = chat
    return update


def make_context(services: BotServices) -> MagicMock:
    context = MagicMock()
    context.application.bot_data = {"services": services, "config": services.config}
    context.bot = AsyncMock()
    context.bot.send_chat_action = AsyncMock()
    return context
