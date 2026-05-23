import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from database import Database
from utils.cache import MemoryCache


class DatabaseMiddleware(BaseMiddleware):
    """Injects db, mem and touches last_seen_at on user interactions."""

    def __init__(self, db: Database, mem: MemoryCache) -> None:
        self._db  = db
        self._mem = mem
        self._touch_cache: dict[int, float] = {}
        self._touch_interval: float = 300.0

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event:   TelegramObject,
        data:    dict[str, Any],
    ) -> Any:
        data["db"]  = self._db
        data["mem"] = self._mem

        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            uid = event.from_user.id
            now = time.monotonic()
            if now - self._touch_cache.get(uid, 0.0) >= self._touch_interval:
                self._touch_cache[uid] = now
                await self._db.touch_user(uid)

        return await handler(event, data)
