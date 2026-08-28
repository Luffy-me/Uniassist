"""Telegram bot application factory and runner."""

from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
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
        .connect_timeout(config.network_timeout_seconds)
        .read_timeout(config.network_timeout_seconds)
        .write_timeout(config.network_timeout_seconds)
        .pool_timeout(config.network_timeout_seconds)
        .get_updates_connect_timeout(config.network_timeout_seconds)
        .get_updates_read_timeout(
            config.network_timeout_seconds + config.poll_timeout_seconds
        )
        .get_updates_write_timeout(config.network_timeout_seconds)
        .get_updates_pool_timeout(config.network_timeout_seconds)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
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
    application.add_error_handler(_handle_error)
    return application


async def _post_shutdown(application: Application) -> None:
    services: BotServices | None = application.bot_data.get("services")
    if services is not None:
        await services.api_client.aclose()


async def _handle_error(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Record handler failures rather than silently dropping an update."""
    update_id = getattr(update, "update_id", "-")
    err = context.error
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
                        "location": "bot.py:_handle_error",
                        "message": "telegram_update_failed",
                        "data": {
                            "update_id": str(update_id),
                            "error_type": type(err).__name__ if err else None,
                            "error": str(err)[:240] if err else None,
                            "has_update": update is not None and update != "-",
                        },
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion
    logger.error(
        "telegram_update_failed update_id=%s",
        update_id,
        exc_info=context.error,
    )


async def _post_init(application: Application) -> None:
    services: BotServices = application.bot_data["services"]
    config: TelegramConfig = application.bot_data["config"]
    await _validate_startup(config, services)


async def _validate_startup(config: TelegramConfig, services: BotServices) -> None:
    if not await services.api_client.health():
        raise SystemExit(
            "UniAssist API is not reachable at "
            f"{config.api_url}. Start FastAPI before the Telegram bot."
        )


def run_bot() -> None:
    """Load configuration and start Telegram long polling."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        config = TelegramConfig.from_env()
    except TelegramConfigError as exc:
        raise SystemExit(str(exc)) from exc

    services = build_services(config)
    application = create_bot(config, services=services)
    logger.info("telegram_bot_start api_url=%s", config.api_url)
    application.run_polling(
        drop_pending_updates=True,
        timeout=config.poll_timeout_seconds,
        bootstrap_retries=config.bootstrap_retries,
    )


if __name__ == "__main__":
    run_bot()
