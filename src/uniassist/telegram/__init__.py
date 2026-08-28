"""Telegram student bot client for UniAssist."""

from uniassist.telegram.config import TelegramConfig

__all__ = ["TelegramConfig", "create_bot", "run_bot"]


def __getattr__(name: str):
    if name in {"create_bot", "run_bot"}:
        from uniassist.telegram import bot

        return getattr(bot, name)
    raise AttributeError(name)
