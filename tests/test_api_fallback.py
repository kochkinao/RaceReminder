import json

import pytest

import utils.api as api
from utils.cache import MemoryCache


class _DummyDb:
    def __init__(self, fresh=None, stale=None):
        self.fresh = fresh
        self.stale = stale
        self.saved = []

    async def get_cache(self, key: str, ttl_seconds: int):
        return self.fresh

    async def get_cache_stale(self, key: str, max_age_seconds: int):
        return self.stale

    async def set_cache(self, key: str, value: str):
        self.saved.append((key, value))


@pytest.mark.asyncio
async def test_cached_uses_stale_fallback_on_fetch_error(monkeypatch) -> None:
    mem = MemoryCache()
    db = _DummyDb(stale=json.dumps([{"id": "session-1"}]))
    api._fallback_stats.update(count=0, last_at=0.0, last_key="")

    class _BrokenSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def fake_client_session():
        return _BrokenSession()

    async def fake_get_token(_http):
        raise RuntimeError("api down")

    monkeypatch.setattr(api.aiohttp, "ClientSession", fake_client_session)
    monkeypatch.setattr(api, "_get_token", fake_get_token)

    data = await api._cached("sessions:test", 3600, mem, db, lambda h, t: [])

    assert data == [{"id": "session-1"}]
    assert api.fallback_stats()["count"] == 1
    assert api.fallback_stats()["last_key"] == "sessions:test"
    assert mem.get("sessions:test") == [{"id": "session-1"}]


@pytest.mark.asyncio
async def test_cached_raises_when_no_stale_fallback_exists(monkeypatch) -> None:
    mem = MemoryCache()
    db = _DummyDb()

    class _BrokenSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def fake_client_session():
        return _BrokenSession()

    async def fake_get_token(_http):
        raise RuntimeError("api down")

    monkeypatch.setattr(api.aiohttp, "ClientSession", fake_client_session)
    monkeypatch.setattr(api, "_get_token", fake_get_token)

    with pytest.raises(RuntimeError):
        await api._cached("sessions:test", 3600, mem, db, lambda h, t: [])
