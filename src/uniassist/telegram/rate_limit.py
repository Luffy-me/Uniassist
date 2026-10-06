"""Lightweight in-memory rate limiter for Telegram users."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from uniassist.telegram.errors import RateLimitExceededError

_EVICT_THRESHOLD = 1000


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
            self._evict_idle(window_start)
            events = self._events[user_id]
            while events and events[0] < window_start:
                events.popleft()
            if len(events) >= self._limit:
                raise RateLimitExceededError
            events.append(now)

    def _evict_idle(self, window_start: float) -> None:
        """Forget users whose last request is outside the window."""
        if len(self._events) < _EVICT_THRESHOLD:
            return
        idle = [
            user_id
            for user_id, events in self._events.items()
            if not events or events[-1] < window_start
        ]
        for user_id in idle:
            del self._events[user_id]

    def reset(self) -> None:
        """Clear all tracked events (for tests)."""
        self._events.clear()
