"""Telegram bot application factory and runner."""

from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from uniassist.telegram.config import TelegramConfig, TelegramConfigError
from uniassist.telegram.handlers import (
    BotServices,
    build_services,
    help_command,
    start_command,
    status_command,
    text_question,
    unknown_command,
    unsupported_message,
)

logger = logging.getLogger("uniassist.telegram")


def create_bot(
    config: TelegramConfig,
    *,
    services: BotServices | None = None,
) -> Application:
    """Create a configured Telegram bot application without starting polling."""
    resolved_services = services or build_services(config)
    application = (
        Application.builder()
        .token(config.bot_token)
        .build()
    )
    application.bot_data["services"] = resolved_services
    application.bot_data["config"] = config

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(
        MessageHandler(filters.COMMAND, unknown_command),
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_question),
    )
    application.add_handler(
        MessageHandler(
            filters.VOICE
            | filters.PHOTO
            | filters.Document.ALL
            | filters.Sticker.ALL,
            unsupported_message,
        ),
    )
    return application


async def _post_shutdown(application: Application) -> None:
    services: BotServices | None = application.bot_data.get("services")
    if services is not None:
        await services.api_client.aclose()


async def _validate_startup(config: TelegramConfig, services: BotServices) -> None:
    if not await services.api_client.health():
        raise SystemExit(
            "UniAssist API is not reachable at "
            f"{config.api_url}. Start FastAPI before the Telegram bot."
        )


def run_bot() -> None:
    """Load configuration and start Telegram long polling."""
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
    )
    try:
        config = TelegramConfig.from_env()
    except TelegramConfigError as exc:
        raise SystemExit(str(exc)) from exc

    services = build_services(config)
    asyncio.run(_validate_startup(config, services))
    application = create_bot(config, services=services)
    application.post_shutdown(_post_shutdown)
    logger.info("telegram_bot_start api_url=%s", config.api_url)
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    run_bot()
