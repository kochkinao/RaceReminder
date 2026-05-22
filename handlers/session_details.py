import json
import logging
import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import utils
from database import Database
from utils.cache import MemoryCache

log = logging.getLogger(__name__)
router = Router()
_REMINDER_OFFSETS = {"1day": 86_400, "1hour": 3_600, "start": 0}
_REMINDER_LABELS = {"1day": "за сутки", "1hour": "за час", "start": "на старт"}


def _reminder_target_ts(session: dict, remind_type: str) -> int | None:
    start_ts = int(session.get("start", 0) or 0)
    if not start_ts or remind_type not in _REMINDER_OFFSETS:
        return None
    return start_ts - _REMINDER_OFFSETS[remind_type]


async def _render_reminder_menu(
    callback: CallbackQuery,
    db: Database,
    mem: MemoryCache,
    session_id: str,
    notice: str | None = None,
) -> None:
    session, _, _ = await utils.load_session_context(db, mem, session_id)
    if not session:
        await callback.answer("Сессия не найдена", show_alert=True)
        return

    reminders = await db.get_session_reminders(callback.from_user.id, session_id)
    active_types = {row["remind_type"] for row in reminders}
    start_ts = session.get("start", 0)
    title = session.get("name", "Сессия")
    user = await db.get_user(callback.from_user.id)
    text = (
        f"🔔 <b>Персональные напоминания</b>\n\n"
        f"<b>{title}</b>\n"
        f"Старт: <code>{utils.fmt_datetime(start_ts, user['timezone'])}</code>\n\n"
        f"Выберите напоминания, которые хотите получать именно по этой сессии."
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=utils.reminder_menu(session_id, active_types),
    )
    await callback.answer(notice or "")


async def _render_session(
    callback: CallbackQuery,
    db: Database,
    mem: MemoryCache,
    session_id: str,
    notice: str | None = None,
) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    session, broadcasts, live_timings = await utils.load_session_context(db, mem, session_id)
    if not session:
        await callback.answer("Сессия не найдена", show_alert=True)
        return

    langs = json.loads(user.get("preferred_langs", '["English"]'))
    card = utils.session_card(
        session,
        broadcasts=broadcasts,
        live_timings=live_timings,
        user_tz=user["timezone"],
        user_langs=langs,
        show_no_bc=bool(user.get("show_no_broadcast", 1)),
    ) or "😕 Для этой сессии нет данных, подходящих под ваши текущие фильтры."

    is_fav = await db.is_favorite(callback.from_user.id, session_id)
    await callback.message.edit_text(
        card,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=utils.session_actions(session_id, is_fav),
    )
    await callback.answer(notice or "")


@router.message(Command("favorites"))
async def cmd_favorites(message: Message, db: Database, mem: MemoryCache) -> None:
    await _show_favorites(message, db, mem)


@router.callback_query(F.data == "favorites")
async def cb_favorites(callback: CallbackQuery, db: Database, mem: MemoryCache) -> None:
    await _show_favorites(callback, db, mem)


async def _show_favorites(target: Message | CallbackQuery, db: Database, mem: MemoryCache) -> None:
    chat_id = target.from_user.id if isinstance(target, CallbackQuery) else target.chat.id
    favorites = await db.get_favorites(chat_id)
    if not favorites:
        text = "❤️ <b>Избранное</b>\n\nПока пусто. Добавляйте интересные сессии из карточки `Подробнее`."
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text, parse_mode="HTML", reply_markup=utils.back_to_menu())
            await target.answer()
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=utils.back_to_menu())
        return

    rows = []
    missing = 0
    for fav in favorites:
        session, _, _ = await utils.load_session_context(db, mem, fav["session_id"])
        if not session:
            missing += 1
            continue
        title = session.get("name", "Сессия")
        rows.append([InlineKeyboardButton(text=title[:48], callback_data=f"session:{fav['session_id']}")])

    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="main_menu")])
    text = "❤️ <b>Избранные сессии</b>"
    if missing:
        text += f"\n\nНекоторые старые сессии ({missing}) уже недоступны в текущих окнах API."
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        await target.answer()
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data.startswith("session:"))
async def cb_session_details(
    callback: CallbackQuery,
    db: Database,
    mem: MemoryCache,
) -> None:
    session_id = callback.data.split(":", 1)[1]
    await _render_session(callback, db, mem, session_id)


@router.callback_query(utils.FavCD.filter())
async def cb_favorite_toggle(
    callback: CallbackQuery,
    callback_data: utils.FavCD,
    db: Database,
    mem: MemoryCache,
) -> None:
    session_id = callback_data.session_id
    if callback_data.action == "remove":
        await db.remove_favorite(callback.from_user.id, session_id)
        notice = "💔 Убрано из избранного"
    else:
        await db.add_favorite(callback.from_user.id, session_id)
        notice = "❤️ Добавлено в избранное"

    await _render_session(callback, db, mem, session_id, notice=notice)


@router.callback_query(utils.RemindCD.filter())
async def cb_session_remind(
    callback: CallbackQuery,
    callback_data: utils.RemindCD,
    db: Database,
    mem: MemoryCache,
) -> None:
    session_id = callback_data.session_id
    if callback_data.action == "menu":
        await _render_reminder_menu(callback, db, mem, session_id)
        return

    session, _, _ = await utils.load_session_context(db, mem, session_id)
    if not session:
        await callback.answer("Сессия не найдена", show_alert=True)
        return

    remind_type = callback_data.remind_type
    target_ts = _reminder_target_ts(session, remind_type)
    if target_ts is None:
        await callback.answer("Не удалось создать напоминание", show_alert=True)
        return
    if target_ts <= int(time.time()):
        await callback.answer("Это время уже прошло для выбранной сессии.", show_alert=True)
        return

    existing = {row["remind_type"] for row in await db.get_session_reminders(callback.from_user.id, session_id)}
    if remind_type in existing:
        await db.remove_session_reminder(callback.from_user.id, session_id, remind_type)
        await _render_reminder_menu(
            callback, db, mem, session_id, notice=f"❌ Напоминание {_REMINDER_LABELS[remind_type]} удалено"
        )
        return

    await db.add_session_reminder(callback.from_user.id, session_id, remind_type, target_ts)
    await _render_reminder_menu(
        callback, db, mem, session_id, notice=f"✅ Напоминание {_REMINDER_LABELS[remind_type]} включено"
    )
