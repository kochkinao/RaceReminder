"""
Two-level cache:
  L1 — in-memory dict (shared across all users in the same process, zero I/O)
  L2 — SQLite api_cache table (survives restarts)

All keys are UTC-aligned so every user hits the same entry.
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

type JsonValue = Any


@dataclass
class _Entry:
    value: JsonValue
    expires_at: float   # monotonic seconds


class MemoryCache:
    """
    Process-wide in-memory cache. One instance created in main.py,
    injected via CacheMiddleware into data['cache'].
    """

    def __init__(self) -> None:
        self._store: dict[str, _Entry] = {}

    def get(self, key: str) -> JsonValue | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: JsonValue, ttl: int) -> None:
        self._store[key] = _Entry(value=value, expires_at=time.monotonic() + ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def size(self) -> int:
        return len(self._store)

    def evict_expired(self) -> int:
        now = time.monotonic()
        expired = [k for k, e in self._store.items() if now > e.expires_at]
        for k in expired:
            del self._store[k]
        return len(expired)
