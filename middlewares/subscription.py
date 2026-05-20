from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, Message, TelegramObject,
)

from config import CHANNEL_ID, CHANNEL_LINK


class SubscriptionMiddleware(BaseMiddleware):
    """
    If CHANNEL_ID is set, checks that the user is subscribed to the channel
    before letting any message through.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not CHANNEL_ID:
            return await handler(event, data)

        bot: Bot = data["bot"]

        match event:
            case Message():
                user_id = event.from_user.id  # type: ignore[union-attr]
                reply = event.answer
            case CallbackQuery():
                user_id = event.from_user.id  # type: ignore[union-attr]
                reply = event.message.answer  # type: ignore[union-attr]
            case _:
                return await handler(event, data)

        try:
            member = await bot.get_chat_member(CHANNEL_ID, user_id)
            if member.status in ("left", "kicked", "banned"):
                raise ValueError
        except Exception:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="📢 Подписаться на канал",
                    url=CHANNEL_LINK or f"https://t.me/{CHANNEL_ID.lstrip('@')}",
                ),
                InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub"),
            ]])
            await reply(
                "⚠️ Для использования бота необходимо подписаться на наш канал.",
                reply_markup=kb,
            )
            return None

        return await handler(event, data)
