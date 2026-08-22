"""Telegram update handlers."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from uniassist.telegram.api_client import UniAssistAPIClient
from uniassist.telegram.config import TelegramConfig
from uniassist.telegram.errors import (
    EMPTY_MESSAGE_TEXT,
    RATE_LIMIT_MESSAGE,
    UNKNOWN_COMMAND_TEXT,
    UNSUPPORTED_MESSAGE_TEXT,
    RateLimitExceededError,
    UniAssistAPIError,
    map_api_error,
)
from uniassist.telegram.formatting import (
    format_ask_result,
    sanitize_plain_text,
    split_message,
)
from uniassist.telegram.rate_limit import InMemoryRateLimiter
from uniassist.telegram.session import SessionStore

logger = logging.getLogger("uniassist.telegram.handlers")

START_MESSAGE = (
    "Welcome to UniAssist.\n\n"
    "Ask me questions about university rules, procedures, and student regulations.\n\n"
    "Answers are based on verified university documents."
)

HELP_MESSAGE = (
    "Ask a question in normal language about university rules or procedures.\n\n"
    "Answers come from verified university documents. When enough evidence is "
    "available, UniAssist includes source citations.\n\n"
    "If the verified document corpus does not contain sufficient evidence, "
    "UniAssist will say so instead of guessing."
)


@dataclass
class BotServices:
    """Dependencies injected into Telegram handlers."""

    config: TelegramConfig
    api_client: UniAssistAPIClient
    rate_limiter: InMemoryRateLimiter
    session_store: SessionStore


def build_services(config: TelegramConfig) -> BotServices:
    return BotServices(
        config=config,
        api_client=UniAssistAPIClient(
            base_url=config.api_url,
            timeout_seconds=config.request_timeout_seconds,
        ),
        rate_limiter=InMemoryRateLimiter(limit_per_minute=config.rate_limit_per_minute),
        session_store=SessionStore(),
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_text(update, START_MESSAGE)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_text(update, HELP_MESSAGE)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services = _services(context)
    online = await services.api_client.health()
    text = "UniAssist is online." if online else "UniAssist is offline."
    await _reply_text(update, text)


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_text(update, UNKNOWN_COMMAND_TEXT)


async def unsupported_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await _reply_text(update, UNSUPPORTED_MESSAGE_TEXT)


async def text_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services = _services(context)
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if message is None or user is None or chat is None:
        return

    question = (message.text or "").strip()
    if not question:
        await message.reply_text(EMPTY_MESSAGE_TEXT)
        return

    request_id = uuid.uuid4().hex
    try:
        await services.rate_limiter.check(user.id)
    except RateLimitExceededError:
        await message.reply_text(RATE_LIMIT_MESSAGE)
        return

    await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)

    try:
        result = await services.api_client.ask(question, request_id=request_id)
    except UniAssistAPIError as exc:
        mapped = map_api_error(exc)
        logger.warning(
            "telegram_api_error request_id=%s status=%s error=%s",
            mapped.request_id or request_id,
            exc.status_code,
            exc.error_code or "-",
        )
        await message.reply_text(mapped.text)
        return

    await services.session_store.touch(user.id, request_id=result.request_id)
    body = sanitize_plain_text(format_ask_result(result))
    for chunk in split_message(body, max_length=services.config.max_message_length):
        await message.reply_text(chunk)

    logger.info(
        "telegram_answer request_id=%s status=%s verified=%s",
        result.request_id,
        result.status,
        result.verified,
    )


def _services(context: ContextTypes.DEFAULT_TYPE) -> BotServices:
    services = context.application.bot_data.get("services")
    if services is None:
        raise RuntimeError("bot services are not configured")
    return services


async def _reply_text(update: Update, text: str) -> None:
    message = update.effective_message
    if message is not None:
        await message.reply_text(text)
