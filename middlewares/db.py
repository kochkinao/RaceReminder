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

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event:   TelegramObject,
        data:    dict[str, Any],
    ) -> Any:
        data["db"]  = self._db
        data["mem"] = self._mem

        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            await self._db.touch_user(event.from_user.id)

        return await handler(event, data)
