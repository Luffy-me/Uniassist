"""Tests for Telegram handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.error import TimedOut

from tests.telegram.conftest import make_context, make_update
from uniassist.telegram.api_client import AskResult, CitationPayload
from uniassist.telegram.errors import (
    EMPTY_MESSAGE_TEXT,
    RATE_LIMIT_MESSAGE,
    REFUSAL_MESSAGE,
    UNKNOWN_COMMAND_TEXT,
    UNSUPPORTED_MESSAGE_TEXT,
    UniAssistAPIError,
)
from uniassist.telegram.handlers import (
    BotServices,
    help_command,
    start_command,
    status_command,
    text_question,
    unknown_command,
    unsupported_message,
)


@pytest.mark.asyncio
async def test_start_command(bot_services: BotServices) -> None:
    update = make_update(text="/start")
    context = make_context(bot_services)
    await start_command(update, context)
    reply = update.effective_message.reply_text
    reply.assert_awaited_once()
    assert "Welcome to UniAssist" in reply.await_args.args[0]
    assert "Добро пожаловать в UniAssist" in reply.await_args.args[0]


@pytest.mark.asyncio
async def test_help_command(bot_services: BotServices) -> None:
    update = make_update(text="/help")
    context = make_context(bot_services)
    await help_command(update, context)
    text = update.effective_message.reply_text.await_args.args[0]
    assert "verified university documents" in text
    assert "проверенных университетских документов" in text
    assert "не будет догадываться" in text


@pytest.mark.asyncio
async def test_status_command_online(bot_services: BotServices) -> None:
    bot_services.api_client.health = AsyncMock(return_value=True)
    update = make_update(text="/status")
    context = make_context(bot_services)
    await status_command(update, context)
    assert "online" in update.effective_message.reply_text.await_args.args[0]
    assert "работает" in update.effective_message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_unknown_command(bot_services: BotServices) -> None:
    update = make_update(text="/unknown")
    context = make_context(bot_services)
    await unknown_command(update, context)
    reply = update.effective_message.reply_text
    assert reply.await_args.args[0] == UNKNOWN_COMMAND_TEXT


@pytest.mark.asyncio
async def test_unsupported_message(bot_services: BotServices) -> None:
    update = make_update(text="ignored")
    context = make_context(bot_services)
    await unsupported_message(update, context)
    assert (
        update.effective_message.reply_text.await_args.args[0]
        == UNSUPPORTED_MESSAGE_TEXT
    )


@pytest.mark.asyncio
async def test_text_question_verified_answer(bot_services: BotServices) -> None:
    bot_services.api_client.ask = AsyncMock(
        return_value=AskResult(
            request_id="req-verified",
            status="verified",
            answer="Students may request academic leave.",
            citations=(
                CitationPayload(
                    chunk_id="c1",
                    document_id="d1",
                    title="Academic Leave Regulations",
                    page_number=4,
                    section=None,
                    source="TEST",
                    source_url="https://example.org/leave",
                    label="Academic Leave Regulations — p. 4",
                ),
            ),
            verified=True,
        )
    )
    update = make_update(text="Can I take academic leave?")
    context = make_context(bot_services)
    await text_question(update, context)
    sent = update.effective_message.reply_text.await_args_list[-1].args[0]
    assert "Students may request academic leave." in sent
    assert "Sources / Источники:" in sent
    assert "https://example.org/leave" in sent
    session = await bot_services.session_store.get(42)
    assert session is not None
    assert session.last_request_id == "req-verified"


@pytest.mark.asyncio
async def test_text_question_refusal(bot_services: BotServices) -> None:
    bot_services.api_client.ask = AsyncMock(
        return_value=AskResult(
            request_id="req-refused",
            status="refused",
            message=REFUSAL_MESSAGE,
            verified=False,
        )
    )
    update = make_update(text="Moon travel policy?")
    context = make_context(bot_services)
    await text_question(update, context)
    sent = update.effective_message.reply_text.await_args.args[0]
    assert REFUSAL_MESSAGE in sent


@pytest.mark.asyncio
async def test_text_question_empty_message(bot_services: BotServices) -> None:
    update = make_update(text="   ")
    context = make_context(bot_services)
    await text_question(update, context)
    assert update.effective_message.reply_text.await_args.args[0] == EMPTY_MESSAGE_TEXT


@pytest.mark.asyncio
async def test_text_question_api_error(bot_services: BotServices) -> None:
    bot_services.api_client.ask = AsyncMock(
        side_effect=UniAssistAPIError("fail", status_code=500, request_id="req-500")
    )
    update = make_update(text="Question?")
    context = make_context(bot_services)
    await text_question(update, context)
    reply_text = update.effective_message.reply_text.await_args.args[0]
    assert "temporarily unavailable" in reply_text


@pytest.mark.asyncio
async def test_text_question_api_429(bot_services: BotServices) -> None:
    bot_services.api_client.ask = AsyncMock(
        side_effect=UniAssistAPIError("too many", status_code=429, request_id="req-429")
    )
    update = make_update(text="Question?")
    context = make_context(bot_services)
    await text_question(update, context)
    assert "too quickly" in update.effective_message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_text_question_rate_limit(bot_services: BotServices) -> None:
    update = make_update(text="Question?")
    context = make_context(bot_services)
    bot_services.api_client.ask = AsyncMock(
        return_value=AskResult(
            request_id="req-1",
            status="verified",
            answer="Answer",
            verified=True,
        )
    )
    for _ in range(3):
        await text_question(update, context)
    await text_question(update, context)
    assert RATE_LIMIT_MESSAGE in update.effective_message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_text_question_propagates_request_id(bot_services: BotServices) -> None:
    bot_services.api_client.ask = AsyncMock(
        return_value=AskResult(
            request_id="generated-req",
            status="verified",
            answer="Answer",
            verified=True,
        )
    )
    update = make_update(text="Question?")
    context = make_context(bot_services)
    with patch("uniassist.telegram.handlers.uuid.uuid4") as uuid4:
        mock_uuid = MagicMock()
        mock_uuid.hex = "client-req"
        uuid4.return_value = mock_uuid
        await text_question(update, context)
    bot_services.api_client.ask.assert_awaited_with(
        "Question?",
        request_id="client-req",
    )


@pytest.mark.asyncio
async def test_text_question_splits_long_answer(bot_services: BotServices) -> None:
    long_answer = "Sentence. " * 120
    bot_services.api_client.ask = AsyncMock(
        return_value=AskResult(
            request_id="req-long",
            status="verified",
            answer=long_answer,
            verified=True,
        )
    )
    update = make_update(text="Long question?")
    context = make_context(bot_services)
    await text_question(update, context)
    assert update.effective_message.reply_text.await_count >= 2


@pytest.mark.asyncio
async def test_text_question_sends_typing_action(bot_services: BotServices) -> None:
    bot_services.api_client.ask = AsyncMock(
        return_value=AskResult(
            request_id="req-typing",
            status="verified",
            answer="Answer",
            verified=True,
        )
    )
    update = make_update(text="Question?")
    context = make_context(bot_services)
    await text_question(update, context)
    assert context.bot.send_chat_action.await_count >= 1


@pytest.mark.asyncio
async def test_text_question_answers_when_typing_action_times_out(
    bot_services: BotServices,
) -> None:
    bot_services.api_client.ask = AsyncMock(
        return_value=AskResult(
            request_id="req-typing-timeout",
            status="verified",
            answer="Answer",
            verified=True,
        )
    )
    update = make_update(text="Question?")
    context = make_context(bot_services)
    context.bot.send_chat_action = AsyncMock(side_effect=TimedOut("typing timed out"))

    await text_question(update, context)

    bot_services.api_client.ask.assert_awaited_once()
    assert update.effective_message.reply_text.await_args.args[0] == "Answer"
