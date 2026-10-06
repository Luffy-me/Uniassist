"""Tests for in-memory rate limiting."""

from __future__ import annotations

import pytest

from uniassist.telegram.errors import RateLimitExceededError
from uniassist.telegram.rate_limit import InMemoryRateLimiter


@pytest.mark.asyncio
async def test_rate_limit_allows_under_threshold() -> None:
    limiter = InMemoryRateLimiter(limit_per_minute=2)
    await limiter.check(42)
    await limiter.check(42)


@pytest.mark.asyncio
async def test_rate_limit_blocks_excess_requests() -> None:
    limiter = InMemoryRateLimiter(limit_per_minute=2)
    await limiter.check(42)
    await limiter.check(42)
    with pytest.raises(RateLimitExceededError):
        await limiter.check(42)


@pytest.mark.asyncio
async def test_rate_limit_is_per_user() -> None:
    limiter = InMemoryRateLimiter(limit_per_minute=1)
    await limiter.check(1)
    await limiter.check(2)


async def test_idle_users_are_evicted() -> None:
    from uniassist.telegram import rate_limit

    limiter = rate_limit.InMemoryRateLimiter(limit_per_minute=5)
    for user_id in range(rate_limit._EVICT_THRESHOLD + 5):
        limiter._events[user_id].append(-1000.0)
    await limiter.check(10_000_000)
    assert len(limiter._events) < rate_limit._EVICT_THRESHOLD
