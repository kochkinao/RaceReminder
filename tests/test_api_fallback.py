import json
import socket

import pytest
from aiohttp import ClientConnectorError

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


def test_unframe_rejects_incomplete_header() -> None:
    with pytest.raises(ValueError, match="Incomplete gRPC-Web frame header"):
        api._unframe(b"\x00\x00\x00")


def test_unframe_rejects_incomplete_payload() -> None:
    with pytest.raises(ValueError, match="Incomplete gRPC-Web frame payload"):
        api._unframe(b"\x00\x00\x00\x00\x05abc")


def test_decode_jwt_payload_rejects_invalid_token() -> None:
    with pytest.raises(ValueError, match="Invalid JWT format"):
        api._decode_jwt_payload("broken-token")


def test_is_expected_api_failure_matches_dns_errors() -> None:
    exc = ClientConnectorError(None, socket.gaierror(socket.EAI_NONAME, "Name or service not known"))

    assert api.is_expected_api_failure(exc) is True


def test_is_expected_api_failure_rejects_generic_errors() -> None:
    assert api.is_expected_api_failure(RuntimeError("boom")) is False


@pytest.mark.asyncio
async def test_cached_ignores_corrupted_fresh_cache_and_refetches(monkeypatch) -> None:
    mem = MemoryCache()
    db = _DummyDb(fresh="{broken", stale=None)

    class _BrokenSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def fake_client_session():
        return _BrokenSession()

    async def fake_get_token(_http):
        return "token"

    async def fake_fetch(_http, _token):
        return [{"id": "session-2"}]

    monkeypatch.setattr(api.aiohttp, "ClientSession", fake_client_session)
    monkeypatch.setattr(api, "_get_token", fake_get_token)

    data = await api._cached("sessions:test", 3600, mem, db, fake_fetch)

    assert data == [{"id": "session-2"}]
    assert db.saved == [("sessions:test", json.dumps([{"id": "session-2"}], ensure_ascii=False))]


@pytest.mark.asyncio
async def test_cached_raises_on_corrupted_stale_cache(monkeypatch) -> None:
    mem = MemoryCache()
    db = _DummyDb(stale="{broken")

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

    with pytest.raises(ValueError, match="Corrupted cache entry"):
        await api._cached("sessions:test", 3600, mem, db, lambda h, t: [])


@pytest.mark.asyncio
async def test_warm_up_returns_none_on_expected_api_failure(monkeypatch) -> None:
    mem = MemoryCache()
    db = _DummyDb()

    async def fake_get_sessions(*_args, **_kwargs):
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    monkeypatch.setattr(api, "get_sessions", fake_get_sessions)

    assert await api.warm_up(mem, db, object()) is None


@pytest.mark.asyncio
async def test_post_raw_retries_without_cookies_on_auth_like_failure(monkeypatch) -> None:
    calls = []

    class FakeResponse:
        def __init__(self, status: int, body: bytes) -> None:
            self.status = status
            self._body = body
            self.request_info = None
            self.history = ()

        async def __aenter__(self):
            if self.status >= 400:
                raise api.aiohttp.ClientResponseError(
                    self.request_info,
                    self.history,
                    status=self.status,
                    message="boom",
                )
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self):
            return None

        async def read(self):
            return self._body

    class FakeSession:
        def post(self, url, *, data, headers, cookies):
            calls.append(cookies)
            if len(calls) == 1:
                return FakeResponse(403, b"")
            return FakeResponse(200, b"ok")

    raw = await api._post_raw(FakeSession(), "ListSeries", b"payload")

    assert raw == b"ok"
    assert calls[0] == api._COOKIES
    assert calls[1] is None
