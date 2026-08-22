"""Telegram student bot client for UniAssist."""

from uniassist.telegram.bot import create_bot, run_bot
from uniassist.telegram.config import TelegramConfig

__all__ = ["TelegramConfig", "create_bot", "run_bot"]
