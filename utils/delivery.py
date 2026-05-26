import json
import time
from dataclasses import dataclass, field
from typing import Any, Hashable

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup, Message


@dataclass(slots=True)
class PendingDelivery:
    kind: str
    chat_id: int
    text: str = ""
    media_type: str = ""
    media_file_id: str = ""
    reply_markup: InlineKeyboardMarkup | None = None
    parse_mode: str = "HTML"
    disable_web_page_preview: bool = True
    dedupe_key: Hashable | None = None
    session_id: str = ""
    notif_type: str = ""
    remind_type: str = ""
    digest_session_ids: tuple[str, ...] = ()
    attempts: int = 0
    next_attempt_at: float = field(default_factory=time.time)
    last_error: str = ""
    queue_id: int = 0


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


def _json_ready(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(val) for key, val in value.items()}
    return value


def dedupe_token(key: Hashable | None) -> str | None:
    if key is None:
        return None
    return json.dumps(_json_ready(key), ensure_ascii=False, separators=(",", ":"))


def pending_delivery_payload(item: PendingDelivery) -> dict[str, Any]:
    return {
        "kind": item.kind,
        "chat_id": item.chat_id,
        "text": item.text,
        "media_type": item.media_type,
        "media_file_id": item.media_file_id,
        "reply_markup": _markup_payload(item.reply_markup),
        "parse_mode": item.parse_mode,
        "disable_web_page_preview": item.disable_web_page_preview,
        "dedupe_key": _json_ready(item.dedupe_key),
        "session_id": item.session_id,
        "notif_type": item.notif_type,
        "remind_type": item.remind_type,
        "digest_session_ids": list(item.digest_session_ids),
    }


def pending_delivery_from_payload(
    payload: dict[str, Any],
    *,
    queue_id: int = 0,
    attempts: int = 0,
    next_attempt_at: float = 0,
    last_error: str = "",
) -> PendingDelivery:
    markup_payload = payload.get("reply_markup")
    reply_markup = InlineKeyboardMarkup.model_validate(markup_payload) if markup_payload else None
    dedupe_key = payload.get("dedupe_key")
    if isinstance(dedupe_key, list):
        dedupe_key = tuple(dedupe_key)
    digest_session_ids = payload.get("digest_session_ids") or ()
    return PendingDelivery(
        kind=payload["kind"],
        chat_id=int(payload["chat_id"]),
        text=payload.get("text", ""),
        media_type=payload.get("media_type", ""),
        media_file_id=payload.get("media_file_id", ""),
        reply_markup=reply_markup,
        parse_mode=payload.get("parse_mode", "HTML"),
        disable_web_page_preview=bool(payload.get("disable_web_page_preview", True)),
        dedupe_key=dedupe_key,
        session_id=payload.get("session_id", ""),
        notif_type=payload.get("notif_type", ""),
        remind_type=payload.get("remind_type", ""),
        digest_session_ids=tuple(digest_session_ids),
        attempts=attempts,
        next_attempt_at=next_attempt_at,
        last_error=last_error,
        queue_id=queue_id,
    )


async def send_delivery(bot: Bot, item: PendingDelivery) -> DeliveryResult:
    try:
        if item.media_type == "photo":
            await bot.send_photo(
                item.chat_id,
                item.media_file_id,
                caption=item.text or None,
                parse_mode=item.parse_mode,
                reply_markup=item.reply_markup,
            )
        elif item.media_type == "video":
            await bot.send_video(
                item.chat_id,
                item.media_file_id,
                caption=item.text or None,
                parse_mode=item.parse_mode,
                reply_markup=item.reply_markup,
            )
        elif item.media_type == "document":
            await bot.send_document(
                item.chat_id,
                item.media_file_id,
                caption=item.text or None,
                parse_mode=item.parse_mode,
                reply_markup=item.reply_markup,
            )
        else:
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


def _markup_payload(reply_markup: InlineKeyboardMarkup | None) -> dict[str, Any] | None:
    if reply_markup is None:
        return None
    return reply_markup.model_dump(exclude_none=True)


def _message_text(message: Message) -> str | None:
    return message.text or message.caption


def _is_not_modified_error(exc: TelegramBadRequest) -> bool:
    return "message is not modified" in str(exc).lower()


async def safe_edit_text(
    message: Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
    disable_web_page_preview: bool | None = None,
) -> bool:
    current_text = _message_text(message)
    current_markup = _markup_payload(message.reply_markup)
    next_markup = _markup_payload(reply_markup)
    if current_text == text and current_markup == next_markup:
        return False

    try:
        await message.edit_text(
            text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
            reply_markup=reply_markup,
        )
        return True
    except TelegramBadRequest as exc:
        if _is_not_modified_error(exc):
            return False
        raise


async def safe_edit_reply_markup(
    message: Message,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    current_markup = _markup_payload(message.reply_markup)
    next_markup = _markup_payload(reply_markup)
    if current_markup == next_markup:
        return False

    try:
        await message.edit_reply_markup(reply_markup=reply_markup)
        return True
    except TelegramBadRequest as exc:
        if _is_not_modified_error(exc):
            return False
        raise
