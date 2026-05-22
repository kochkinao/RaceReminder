"""
RaceDay.watch gRPC-Web client.
Reverse-engineered from fetch_sessions.py — all field numbers and
encoding verified against real API responses.

Key differences from initial implementation:
  1. Base URL: https://raceday.watch/api/raceday.v5.RaceDay/<Method>
  2. Token: GetAccessToken sends email at field 1, returns raw JWT (not wrapped)
  3. AccessTokenID comes from JWT payload, not from protobuf field
  4. Headers: Origin + Referer + User-Agent required
  5. Cookies: _ga + _ga_QCGJL0F44F required (analytics, but API checks them)
  6. Session field layout: series at field 7, location at field 6 (not 1/3)
  7. Series field layout: vehicleClasses at field 4 (not 1)
  8. Location: 13 fields including alternateName, trackMap, regionName
  9. window_start encoded as plain int64 (field 1), not wrapped
"""
import base64
import json
import logging
import struct
import time
from datetime import UTC, datetime
from typing import Any

import aiohttp

from config import API_BASE_URL, API_FALLBACK_STALE_SECONDS
from database import Database
from utils.cache import MemoryCache

log = logging.getLogger(__name__)

type ApiObject = dict[str, Any]
_fallback_stats = {"count": 0, "last_at": 0.0, "last_key": ""}

# ── TTLs ──────────────────────────────────────────────────────────────────────
_TTL_SERIES   = 6 * 3_600
_TTL_CLASSES  = 24 * 3_600
_TTL_SESSIONS = 3_600
_TTL_BCASTS   = 3_600

# ── Transport constants ───────────────────────────────────────────────────────
_BASE = "https://raceday.watch/api/raceday.v5.RaceDay"

_HEADERS = {
    "Accept":       "*/*",
    "Content-Type": "application/grpc-web+proto",
    "Origin":       "https://raceday.watch",
    "Referer":      "https://raceday.watch/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
    "X-Grpc-Web": "1",
}

# Analytics cookies — API validates their presence
_COOKIES = {
    "_ga":              "GA1.1.1231997137.1778836345",
    "_ga_QCGJL0F44F":  "GS2.1.s1778836344$o1$g1$t1778838105$j26$l0$h0",
}

# ── Protobuf encoding ─────────────────────────────────────────────────────────

def _varint(value: int) -> bytes:
    if value < 0:
        value += 1 << 64
    out = bytearray()
    while True:
        bits = value & 0x7F
        value >>= 7
        out.append(bits | (0x80 if value else 0))
        if not value:
            break
    return bytes(out)

def _key(field: int, wire_type: int) -> bytes:
    return _varint((field << 3) | wire_type)

def _str(field: int, value: str) -> bytes:
    raw = value.encode()
    return _key(field, 2) + _varint(len(raw)) + raw

def _msg(field: int, value: bytes) -> bytes:
    return _key(field, 2) + _varint(len(value)) + value

def _int64(field: int, value: int) -> bytes:
    return _key(field, 0) + _varint(value)

# Wrapped scalar types (google.protobuf.StringValue etc.)
def _str_val(s: str) -> bytes:   return _str(1, s)
def _int64_val(n: int) -> bytes: return _int64(1, n)


# ── Protobuf decoding ─────────────────────────────────────────────────────────

def _parse(buf: bytes) -> list[tuple[int, int, Any]]:
    items: list[tuple[int, int, Any]] = []
    offset = 0
    while offset < len(buf):
        key, offset = _parse_varint(buf, offset)
        fn, wt = key >> 3, key & 0x07
        match wt:
            case 0:
                val, offset = _parse_varint(buf, offset)
                items.append((fn, wt, val))
            case 1:
                val = struct.unpack("<d", buf[offset: offset + 8])[0]
                offset += 8
                items.append((fn, wt, val))
            case 2:
                ln, offset = _parse_varint(buf, offset)
                items.append((fn, wt, buf[offset: offset + ln]))
                offset += ln
            case 5:
                val = struct.unpack("<I", buf[offset: offset + 4])[0]
                offset += 4
                items.append((fn, wt, val))
            case _:
                break
    return items

def _parse_varint(buf: bytes, offset: int) -> tuple[int, int]:
    result, shift = 0, 0
    while True:
        b = buf[offset]; offset += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, offset
        shift += 7

# Unwrappers for google.protobuf wrapper types
def _unwrap_str(buf: bytes) -> str | None:
    for fn, wt, val in _parse(buf):
        if fn == 1 and wt == 2:
            return val.decode()
    return None

def _unwrap_int(buf: bytes) -> int | None:
    for fn, wt, val in _parse(buf):
        if fn == 1 and wt == 0:
            return val
    return None

def _unwrap_double(buf: bytes) -> float | None:
    for fn, wt, val in _parse(buf):
        if fn == 1 and wt == 1:
            return val
    return None

def _unwrap_bool(buf: bytes) -> bool | None:
    for fn, wt, val in _parse(buf):
        if fn == 1 and wt == 0:
            return bool(val)
    return None


# ── Object parsers (field numbers verified against fetch_sessions.py) ─────────

def _vehicle_class(buf: bytes) -> ApiObject:
    obj: ApiObject = {}
    for fn, wt, val in _parse(buf):
        match fn, wt:
            case 1, 2: obj["id"]          = _unwrap_str(val)
            case 2, 2: obj["name"]        = val.decode()
            case 3, 2: obj["description"] = _unwrap_str(val)
    return obj


def _series(buf: bytes) -> ApiObject:
    """
    field 1 = id          (StringValue)
    field 2 = name        (plain string)
    field 3 = description (StringValue)
    field 4 = vehicleClasses[] (message)   ← was field 1 in our old code!
    field 5 = isEsports   (bool)
    field 6 = infoLink    (StringValue)
    """
    obj: ApiObject = {"vehicleClasses": []}
    for fn, wt, val in _parse(buf):
        match fn, wt:
            case 1, 2: obj["id"]          = _unwrap_str(val)
            case 2, 2: obj["name"]        = val.decode()
            case 3, 2: obj["description"] = _unwrap_str(val)
            case 4, 2: obj["vehicleClasses"].append(_vehicle_class(val))
            case 5, 0: obj["isEsports"]   = bool(val)
            case 6, 2: obj["infoLink"]    = _unwrap_str(val)
    return obj


def _location(buf: bytes) -> ApiObject:
    """
    field 1  = id           (StringValue)
    field 2  = name         (plain string)
    field 3  = notes        (StringValue)
    field 4  = alternateName(StringValue)
    field 5  = address      (StringValue)
    field 6  = country      (StringValue)
    field 7  = yearOpened   (Int32Value)
    field 8  = yearClosed   (Int32Value)
    field 9  = infoLink     (StringValue)
    field 10 = trackMap     (StringValue)
    field 11 = lat          (DoubleValue)
    field 12 = lon          (DoubleValue)
    field 13 = regionName   (StringValue)
    """
    obj: ApiObject = {}
    for fn, wt, val in _parse(buf):
        match fn, wt:
            case 1,  2: obj["id"]            = _unwrap_str(val)
            case 2,  2: obj["name"]          = val.decode()
            case 3,  2: obj["notes"]         = _unwrap_str(val)
            case 4,  2: obj["alternateName"] = _unwrap_str(val)
            case 5,  2: obj["address"]       = _unwrap_str(val)
            case 6,  2: obj["country"]       = _unwrap_str(val)
            case 7,  2: obj["yearOpened"]    = _unwrap_int(val)
            case 8,  2: obj["yearClosed"]    = _unwrap_int(val)
            case 9,  2: obj["infoLink"]      = _unwrap_str(val)
            case 10, 2: obj["trackMap"]      = _unwrap_str(val)
            case 11, 2: obj["lat"]           = _unwrap_double(val)
            case 12, 2: obj["lon"]           = _unwrap_double(val)
            case 13, 2: obj["regionName"]    = _unwrap_str(val)
    return obj


def _session(buf: bytes) -> ApiObject:
    """
    field 1  = id              (StringValue)
    field 2  = name            (plain string)
    field 3  = start           (plain int64/varint)
    field 4  = durationMinutes (plain varint)
    field 6  = location        (message)     ← field 5 is skipped
    field 7  = series[]        (message)     ← was field 1 in our old code!
    field 8  = notes           (StringValue)
    field 9  = status          (varint)
    field 10 = isEsports       (bool)
    """
    obj: ApiObject = {"series": []}
    for fn, wt, val in _parse(buf):
        match fn, wt:
            case 1,  2: obj["id"]              = _unwrap_str(val)
            case 2,  2: obj["name"]            = val.decode()
            case 3,  0: obj["start"]           = val
            case 4,  0: obj["durationMinutes"] = val
            case 6,  2: obj["location"]        = _location(val)
            case 7,  2: obj["series"].append(_series(val))
            case 8,  2: obj["notes"]           = _unwrap_str(val)
            case 9,  0: obj["status"]          = val
            case 10, 0: obj["isEsports"]       = bool(val)

    if ts := obj.get("start"):
        obj["startIsoUtc"] = datetime.fromtimestamp(ts, UTC).isoformat().replace("+00:00", "Z")

    return obj


def _broadcast(buf: bytes) -> ApiObject:
    obj: ApiObject = {"langIds": []}
    for fn, wt, val in _parse(buf):
        match fn, wt:
            case 1, 2: obj["id"]           = _unwrap_str(val)
            case 2, 0: obj["type"]         = val
            case 3, 2: obj["session"]      = _session(val)
            case 4, 2: obj["langIds"].append(val.decode())
            case 5, 2: obj["description"]  = _unwrap_str(val)
            case 6, 2: obj["url"]          = _unwrap_str(val)
            case 7, 2: obj["isGeoblocked"] = _unwrap_bool(val)
            case 8, 2: obj["isPaid"]       = _unwrap_bool(val)
    return obj


def _live_timing(buf: bytes) -> ApiObject:
    obj: ApiObject = {}
    for fn, wt, val in _parse(buf):
        match fn, wt:
            case 1, 2: obj["id"]          = _unwrap_str(val)
            case 2, 2: obj["sessionId"]   = val.decode()
            case 3, 2: obj["description"] = _unwrap_str(val)
            case 4, 2: obj["url"]         = val.decode()
    return obj


def _vehicle_class_top(buf: bytes) -> ApiObject:
    """ListVehicleClasses top-level (same structure as embedded)."""
    return _vehicle_class(buf)


def _collect(msg: bytes, field: int, parser) -> list[ApiObject]:
    return [parser(val) for fn, wt, val in _parse(msg) if fn == field and wt == 2]


# ── gRPC-Web framing ──────────────────────────────────────────────────────────

def _frame(proto: bytes) -> bytes:
    return b"\x00" + len(proto).to_bytes(4, "big") + proto


def _unframe(raw: bytes) -> bytes:
    """Extract first non-trailer gRPC-Web frame."""
    offset = 0
    while offset < len(raw):
        flags  = raw[offset]
        length = int.from_bytes(raw[offset + 1: offset + 5], "big")
        offset += 5
        payload = raw[offset: offset + length]
        offset += length
        if not (flags & 0x80):   # 0x80 = trailer frame
            return payload
    raise ValueError("No data frame found in gRPC-Web response")


# ── Token management ──────────────────────────────────────────────────────────

_token_cache: dict[str, str | float] = {}


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    segment = token.split(".")[1]
    segment += "=" * (-len(segment) % 4)
    return json.loads(base64.urlsafe_b64decode(segment).decode())


async def _get_token(session: aiohttp.ClientSession) -> str:
    now = time.time()
    if float(_token_cache.get("expires", 0)) > now + 60:
        return str(_token_cache["token"])

    # Send email as field 1 plain string
    proto = _str(1, "anonymous@raceday.watch")
    async with session.post(
        f"{_BASE}/GetAccessToken",
        data=_frame(proto),
        headers=_HEADERS,
        cookies=_COOKIES,
    ) as resp:
        resp.raise_for_status()
        raw = await resp.read()

    msg = _unframe(raw)

    # Token is a raw JWT string at field 1 (NOT a StringValue wrapper)
    jwt_token = ""
    for fn, wt, val in _parse(msg):
        if fn == 1 and wt == 2:
            jwt_token = val.decode()
            break

    if not jwt_token:
        raise ValueError("GetAccessToken returned no token")

    # AccessTokenID lives inside the JWT payload
    payload     = _decode_jwt_payload(jwt_token)
    token_id    = payload["AccessTokenID"]

    _token_cache.update(token=token_id, expires=now + 3_600)
    log.debug("Token refreshed, ID: %s…", token_id[:8])
    return token_id


async def _post(session: aiohttp.ClientSession, method: str, proto: bytes) -> bytes:
    async with session.post(
        f"{_BASE}/{method}",
        data=_frame(proto),
        headers=_HEADERS,
        cookies=_COOKIES,
    ) as resp:
        resp.raise_for_status()
        return _unframe(await resp.read())


# ── Low-level fetchers ────────────────────────────────────────────────────────

async def _fetch_vehicle_classes(s: aiohttp.ClientSession, tok: str) -> list[ApiObject]:
    return _collect(await _post(s, "ListVehicleClasses", _str(5, tok)), 1, _vehicle_class_top)


async def _fetch_series(s: aiohttp.ClientSession, tok: str, year: str) -> list[ApiObject]:
    proto = _msg(1, _str_val(year)) + _str(2, tok)
    return _collect(await _post(s, "ListSeries", proto), 1, _series)


async def _fetch_sessions(
    s: aiohttp.ClientSession, tok: str,
    window_start: int, window_end: int,
) -> list[ApiObject]:
    """
    field 1 = window_start  plain int64 (NOT wrapped)
    field 2 = window_end    Int64Value  (wrapped)
    field 3 = timezone      StringValue (wrapped) — omitted, UTC assumed
    field 4 = access_token  plain string
    """
    proto = (
        _int64(1, window_start)
        + _msg(2, _int64_val(window_end))
        + _str(4, tok)
    )
    return _collect(await _post(s, "ListSessions", proto), 1, _session)


async def _fetch_broadcasts(
    s: aiohttp.ClientSession, tok: str, window_start: int,
) -> list[ApiObject]:
    proto = _msg(2, _int64_val(window_start)) + _msg(3, b"\x08\x01") + _str(4, tok)
    return _collect(await _post(s, "ListBroadcasts", proto), 1, _broadcast)


async def _fetch_live_timings(
    s: aiohttp.ClientSession, tok: str, session_id: str,
) -> list[ApiObject]:
    proto = _str(1, session_id) + _str(2, tok)
    return _collect(await _post(s, "ListLiveTimings", proto), 1, _live_timing)


# ── Two-level cache core ──────────────────────────────────────────────────────

async def _cached(
    key: str, ttl: int, mem: MemoryCache, db: Database, fetch_fn
) -> Any:
    if (hit := mem.get(key)) is not None:
        log.debug("L1 hit: %s", key)
        return hit
    raw = await db.get_cache(key, ttl)
    if raw is not None:
        log.debug("L2 hit: %s", key)
        data = json.loads(raw)
        mem.set(key, data, ttl)
        return data
    log.info("API fetch: %s", key)
    try:
        async with aiohttp.ClientSession() as http:
            tok = await _get_token(http)
            data = await fetch_fn(http, tok)
        mem.set(key, data, ttl)
        await db.set_cache(key, json.dumps(data, ensure_ascii=False))
        return data
    except Exception as exc:
        stale_raw = await db.get_cache_stale(key, API_FALLBACK_STALE_SECONDS)
        if stale_raw is None:
            raise
        _fallback_stats["count"] += 1
        _fallback_stats["last_at"] = time.time()
        _fallback_stats["last_key"] = key
        log.warning("API fallback to stale cache for %s: %s", key, exc)
        data = json.loads(stale_raw)
        mem.set(key, data, min(ttl, 300))
        return data


# ── Public API ────────────────────────────────────────────────────────────────

async def get_all_series(
    mem: MemoryCache, db: Database, year: str = "2026"
) -> list[ApiObject]:
    return await _cached(
        f"series:{year}", _TTL_SERIES, mem, db,
        lambda h, t: _fetch_series(h, t, year),
    )


async def get_all_vehicle_classes(
    mem: MemoryCache, db: Database
) -> list[ApiObject]:
    return await _cached(
        "vehicle_classes", _TTL_CLASSES, mem, db, _fetch_vehicle_classes
    )


async def get_sessions(
    mem: MemoryCache, db: Database,
    window_start: int, window_end: int,
) -> list[ApiObject]:
    return await _cached(
        f"sessions:{window_start}:{window_end}", _TTL_SESSIONS, mem, db,
        lambda h, t: _fetch_sessions(h, t, window_start, window_end),
    )


async def get_broadcasts(
    mem: MemoryCache, db: Database, window_start: int,
) -> list[ApiObject]:
    return await _cached(
        f"broadcasts:{window_start}", _TTL_BCASTS, mem, db,
        lambda h, t: _fetch_broadcasts(h, t, window_start),
    )


async def get_live_timings(session_id: str) -> list[ApiObject]:
    async with aiohttp.ClientSession() as http:
        tok = await _get_token(http)
        return await _fetch_live_timings(http, tok, session_id)


# ── Warm-up ───────────────────────────────────────────────────────────────────

async def warm_up(mem: MemoryCache, db: Database) -> bool:
    from utils.windows import today_window, week_window, notify_window

    log.info("Cache warm-up started")
    try:
        t_start, t_end = today_window()
        w_start, w_end = week_window()
        n_start, n_end = notify_window()

        await get_sessions(mem, db, t_start, t_end)
        await get_broadcasts(mem, db, t_start)
        await get_sessions(mem, db, w_start, w_end)
        await get_broadcasts(mem, db, w_start)
        await get_sessions(mem, db, n_start, n_end)
        await get_all_series(mem, db)
        await get_all_vehicle_classes(mem, db)

        evicted = mem.evict_expired()
        log.info("Cache warm-up done. L1: %d entries (%d evicted)", mem.size(), evicted)
        return True

    except Exception as exc:
        log.error("Warm-up failed: %s", exc)
        return False


# ── Domain helpers ────────────────────────────────────────────────────────────

def broadcasts_by_session(broadcasts: list[ApiObject]) -> dict[str, list[ApiObject]]:
    index: dict[str, list[ApiObject]] = {}
    for b in broadcasts:
        if sid := b.get("session", {}).get("id", ""):
            index.setdefault(sid, []).append(b)
    return index


def filter_sessions_for_user(
    sessions:   list[ApiObject],
    series_ids: set[str],
    class_ids:  set[str],
) -> list[ApiObject]:
    if not series_ids and not class_ids:
        return []

    def matches(s: ApiObject) -> bool:
        for sr in s.get("series", []):
            if sr.get("id") in series_ids:
                return True
            for vc in sr.get("vehicleClasses", []):
                if vc.get("id") in class_ids:
                    return True
        return False

    result = [s for s in sessions if matches(s)]
    result.sort(key=lambda s: s.get("start", 0))
    return result


def fallback_stats() -> dict[str, Any]:
    return dict(_fallback_stats)
