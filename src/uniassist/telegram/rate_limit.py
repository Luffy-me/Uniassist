"""Lightweight in-memory rate limiter for Telegram users."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from uniassist.telegram.errors import RateLimitExceededError


class InMemoryRateLimiter:
    """Per-user sliding-window rate limiter suitable for single-process deployment."""

    def __init__(self, *, limit_per_minute: int) -> None:
        if limit_per_minute <= 0:
            raise ValueError("limit_per_minute must be positive")
        self._limit = limit_per_minute
        self._events: dict[int, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, user_id: int) -> None:
        """Raise RateLimitExceededError when the user exceeds the limit."""
        now = time.monotonic()
        window_start = now - 60.0
        async with self._lock:
            events = self._events[user_id]
            while events and events[0] < window_start:
                events.popleft()
            if len(events) >= self._limit:
                raise RateLimitExceededError
            events.append(now)

    def reset(self) -> None:
        """Clear all tracked events (for tests)."""
        self._events.clear()
