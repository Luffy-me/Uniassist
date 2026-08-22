"""In-memory Telegram user session tracking."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class UserSession:
    """Lightweight per-user session metadata."""

    telegram_user_id: int
    session_id: str
    last_request_id: str | None
    updated_at: datetime


class SessionStore:
    """Store minimal session metadata in memory for Phase 9."""

    def __init__(self) -> None:
        self._sessions: dict[int, UserSession] = {}
        self._lock = asyncio.Lock()

    async def touch(
        self,
        telegram_user_id: int,
        *,
        request_id: str | None = None,
    ) -> UserSession:
        async with self._lock:
            existing = self._sessions.get(telegram_user_id)
            session_id = existing.session_id if existing else uuid.uuid4().hex
            session = UserSession(
                telegram_user_id=telegram_user_id,
                session_id=session_id,
                last_request_id=request_id,
                updated_at=datetime.now(UTC),
            )
            self._sessions[telegram_user_id] = session
            return session

    async def get(self, telegram_user_id: int) -> UserSession | None:
        async with self._lock:
            return self._sessions.get(telegram_user_id)

    def clear(self) -> None:
        self._sessions.clear()
