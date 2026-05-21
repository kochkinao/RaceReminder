from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from utils.metrics import Metrics


class MetricsMiddleware(BaseMiddleware):
    """Injects metrics into handlers and counts incoming messages/commands."""

    def __init__(self, metrics: Metrics) -> None:
        self._metrics = metrics

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["metrics"] = self._metrics

        if isinstance(event, Message):
            self._metrics.messages_received.inc()
            if event.text and event.text.startswith("/"):
                cmd = event.text.split()[0].lstrip("/").split("@")[0]
                self._metrics.commands[cmd] += 1

        return await handler(event, data)
