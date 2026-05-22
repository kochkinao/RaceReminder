import time
from dataclasses import dataclass, field
from typing import Any, Hashable

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup


@dataclass(slots=True)
class PendingDelivery:
    kind: str
    chat_id: int
    text: str
    reply_markup: InlineKeyboardMarkup | None = None
    parse_mode: str = "HTML"
    disable_web_page_preview: bool = True
    dedupe_key: Hashable | None = None
    session_id: str = ""
    notif_type: str = ""
    remind_type: str = ""
    digest_session_ids: tuple[str, ...] = ()
    attempts: int = 0
    next_attempt_at: float = field(default_factory=time.monotonic)
    last_error: str = ""


@dataclass(slots=True)
class DeliveryResult:
    status: str
    retry_delay: float = 0
    error: str = ""


class DeliveryQueue:
    def __init__(self) -> None:
        self._items: list[PendingDelivery] = []
        self._active_keys: set[Hashable] = set()

    def enqueue(self, item: PendingDelivery, delay_seconds: float = 0) -> bool:
        if item.dedupe_key is not None and item.dedupe_key in self._active_keys:
            return False
        item.next_attempt_at = time.monotonic() + delay_seconds
        self._items.append(item)
        if item.dedupe_key is not None:
            self._active_keys.add(item.dedupe_key)
        return True

    def pop_due(self, limit: int = 100) -> list[PendingDelivery]:
        now = time.monotonic()
        due = [item for item in self._items if item.next_attempt_at <= now][:limit]
        if not due:
            return []
        due_ids = {id(item) for item in due}
        self._items = [item for item in self._items if id(item) not in due_ids]
        return due

    def complete(self, item: PendingDelivery) -> None:
        if item.dedupe_key is not None:
            self._active_keys.discard(item.dedupe_key)

    def has(self, key: Hashable) -> bool:
        return key in self._active_keys

    def requeue(self, item: PendingDelivery, delay_seconds: float) -> None:
        item.next_attempt_at = time.monotonic() + delay_seconds
        self._items.append(item)

    def size(self) -> int:
        return len(self._items)


delivery_queue = DeliveryQueue()


async def send_delivery(bot: Bot, item: PendingDelivery) -> DeliveryResult:
    try:
        await bot.send_message(
            item.chat_id,
            item.text,
            parse_mode=item.parse_mode,
            reply_markup=item.reply_markup,
            disable_web_page_preview=item.disable_web_page_preview,
        )
        return DeliveryResult(status="success")

    except TelegramForbiddenError:
        return DeliveryResult(status="blocked", error="blocked bot")

    except TelegramRetryAfter as exc:
        return DeliveryResult(
            status="retry",
            retry_delay=float(exc.retry_after) + 1,
            error=f"retry after {exc.retry_after}",
        )

    except Exception as exc:
        return DeliveryResult(status="retry", error=str(exc))
