"""Offline failure-mode validation (Phase N, mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.telegram.conftest import make_context, make_update
from uniassist.telegram.errors import SERVICE_UNAVAILABLE_MESSAGE, UniAssistAPIError
from uniassist.telegram.handlers import BotServices, text_question


@pytest.mark.asyncio
async def test_telegram_empty_question(bot_services: BotServices) -> None:
    update = make_update(text="   ")
    context = make_context(bot_services)
    await text_question(update, context)
    assert update.effective_message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_telegram_api_unavailable_maps_to_friendly_error(
    bot_services: BotServices,
) -> None:
    bot_services.api_client.ask = AsyncMock(
        side_effect=UniAssistAPIError("down", status_code=503, request_id="req-503")
    )
    update = make_update(text="Question?")
    context = make_context(bot_services)
    await text_question(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert SERVICE_UNAVAILABLE_MESSAGE in reply
    assert "GROQ" not in reply
