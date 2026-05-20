from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from database import Database
from utils.cache import MemoryCache


class DatabaseMiddleware(BaseMiddleware):
    """Injects ``db`` and ``mem`` (MemoryCache) into every handler."""

    def __init__(self, db: Database, mem: MemoryCache) -> None:
        self._db  = db
        self._mem = mem

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["db"]  = self._db
        data["mem"] = self._mem
        return await handler(event, data)
