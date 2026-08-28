"""Telegram update handlers."""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import suppress
from dataclasses import dataclass

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import TelegramError
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
    "Ask me questions about university rules, procedures, and student "
    "regulations. Answers are based on verified university documents.\n\n"
    "---\n\n"
    "Добро пожаловать в UniAssist.\n\n"
    "Задавайте вопросы о правилах университета, процедурах и студенческих "
    "регламентах. Ответы основаны только на проверенных официальных документах."
)

HELP_MESSAGE = (
    "Ask a question in your own language about university rules or procedures.\n\n"
    "Answers come from verified university documents. When enough evidence is "
    "available, UniAssist includes source citations and the official document URL "
    "when it was recorded.\n\n"
    "If nothing has been published yet, or the documents do not cover your "
    "question, UniAssist will say so instead of guessing.\n\n"
    "Commands: /start /help /status\n\n"
    "---\n\n"
    "Задайте вопрос на своём языке о правилах или процедурах университета.\n\n"
    "Ответы берутся из проверенных университетских документов. Если доказательств "
    "достаточно, UniAssist указывает источники и официальную ссылку, когда она "
    "есть.\n\n"
    "Если документы ещё не опубликованы или в них нет ответа на ваш вопрос, "
    "бот честно скажет об этом и не будет догадываться.\n\n"
    "Команды: /start /help /status"
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
    text = (
        "UniAssist is online.\nUniAssist работает."
        if online
        else "UniAssist is offline.\nUniAssist недоступен."
    )
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
    # #region agent log
    try:
        import json
        import time

        with open("/Users/cleo/Desktop/Uniassist/.cursor/debug-0bf777.log", "a") as _f:
            _f.write(
                json.dumps(
                    {
                        "sessionId": "0bf777",
                        "hypothesisId": "A",
                        "location": "handlers.py:text_question",
                        "message": "text_question_entered",
                        "data": {
                            "has_message": message is not None,
                            "text_len": len((message.text or "").strip())
                            if message
                            else 0,
                            "api_url": services.config.api_url,
                        },
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion
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

    try:
        await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)
    except TelegramError as exc:
        logger.warning(
            "telegram_typing_action_failed request_id=%s error=%s",
            request_id,
            type(exc).__name__,
        )

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _keep_typing(context, chat.id, request_id, stop_typing)
    )
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
    finally:
        stop_typing.set()
        typing_task.cancel()
        with suppress(asyncio.CancelledError):
            await typing_task

    await services.session_store.touch(user.id, request_id=result.request_id)
    body = sanitize_plain_text(format_ask_result(result))
    # #region agent log
    try:
        import json
        import time

        with open("/Users/cleo/Desktop/Uniassist/.cursor/debug-0bf777.log", "a") as _f:
            _f.write(
                json.dumps(
                    {
                        "sessionId": "0bf777",
                        "hypothesisId": "D",
                        "location": "handlers.py:text_question",
                        "message": "ask_ok_sending_reply",
                        "data": {
                            "request_id": result.request_id,
                            "status": result.status,
                            "body_len": len(body),
                        },
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion
    for chunk in split_message(body, max_length=services.config.max_message_length):
        try:
            await message.reply_text(chunk)
        except TelegramError as exc:
            # #region agent log
            try:
                import json
                import time

                with open(
                    "/Users/cleo/Desktop/Uniassist/.cursor/debug-0bf777.log", "a"
                ) as _f:
                    _f.write(
                        json.dumps(
                            {
                                "sessionId": "0bf777",
                                "hypothesisId": "C",
                                "location": "handlers.py:text_question",
                                "message": "answer_reply_failed",
                                "data": {
                                    "error_type": type(exc).__name__,
                                    "error": str(exc)[:240],
                                },
                                "timestamp": int(time.time() * 1000),
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion
            raise

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


async def _keep_typing(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    request_id: str,
    stop: asyncio.Event,
) -> None:
    """Refresh Telegram typing while /ask is in flight (status expires ~5s)."""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=4.0)
        except TimeoutError:
            try:
                await context.bot.send_chat_action(
                    chat_id=chat_id,
                    action=ChatAction.TYPING,
                )
            except TelegramError as exc:
                logger.warning(
                    "telegram_typing_action_failed request_id=%s error=%s",
                    request_id,
                    type(exc).__name__,
                )
                return
        else:
            return


async def _reply_text(update: Update, text: str) -> None:
    message = update.effective_message
    if message is None:
        return
    try:
        await message.reply_text(text)
    except TelegramError:
        raise
