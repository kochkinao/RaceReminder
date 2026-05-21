import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from config import THROTTLE_RATE

log = logging.getLogger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    """Rate-limit each user to one message per THROTTLE_RATE seconds."""

    def __init__(self, rate: float = THROTTLE_RATE) -> None:
        self._rate = rate
        self._locks: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id: int = event.from_user.id  # type: ignore[union-attr]
        now = asyncio.get_running_loop().time()
        last = self._locks.get(user_id, 0.0)

        if now - last < self._rate:
            log.debug("Throttled user %d", user_id)
            return None

        self._locks[user_id] = now
        return await handler(event, data)
