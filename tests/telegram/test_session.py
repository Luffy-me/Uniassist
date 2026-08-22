"""Tests for in-memory session store."""

from __future__ import annotations

import pytest

from uniassist.telegram.session import SessionStore


@pytest.mark.asyncio
async def test_session_store_tracks_request_id() -> None:
    store = SessionStore()
    first = await store.touch(42, request_id="req-1")
    second = await store.touch(42, request_id="req-2")
    assert first.session_id == second.session_id
    assert second.last_request_id == "req-2"
