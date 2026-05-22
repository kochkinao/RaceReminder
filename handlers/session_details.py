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
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    text = (
        f"{utils.tr(lang, 'session.reminder_title')}\n\n"
        f"<b>{title}</b>\n"
        f"{utils.tr(lang, 'session.start')}: <code>{utils.fmt_datetime(start_ts, user['timezone'], lang)}</code>\n\n"
        f"{utils.tr(lang, 'session.reminder_prompt')}"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=utils.reminder_menu(session_id, active_types, lang),
    )
    await callback.answer(notice or "")


async def _render_session(
    callback: CallbackQuery,
    db: Database,
    mem: MemoryCache,
    session_id: str,
    notice: str | None = None,
) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)

    session, broadcasts, live_timings = await utils.load_session_context(db, mem, session_id)
    if not session:
        await callback.answer(utils.tr(lang, "session.not_found"), show_alert=True)
        return

    langs = json.loads(user.get("preferred_langs", '["English"]'))
    card = utils.session_card(
        session,
        broadcasts=broadcasts,
        live_timings=live_timings,
        user_tz=user["timezone"],
        user_langs=langs,
        show_no_bc=bool(user.get("show_no_broadcast", 1)),
        ui_lang=lang,
    ) or utils.tr(lang, "session.no_filtered_data")

    is_fav = await db.is_favorite(callback.from_user.id, session_id)
    await callback.message.edit_text(
        card,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=utils.session_actions(session_id, is_fav, lang),
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
    user = await db.get_or_create_user(chat_id, getattr(getattr(target, "from_user", None), "username", None))
    lang = utils.get_ui_lang(user)
    favorites = await db.get_favorites(chat_id)
    if not favorites:
        text = utils.tr(lang, "favorites.empty")
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text, parse_mode="HTML", reply_markup=utils.back_to_menu(lang))
            await target.answer()
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=utils.back_to_menu(lang))
        return

    rows = []
    missing = 0
    for fav in favorites:
        session, _, _ = await utils.load_session_context(db, mem, fav["session_id"])
        if not session:
            missing += 1
            continue
        title = session.get("name", "Session" if lang == "en" else "Сессия")
        rows.append([InlineKeyboardButton(text=title[:48], callback_data=f"session:{fav['session_id']}")])

    rows.append([InlineKeyboardButton(text=utils.tr(lang, "menu.back_to_menu"), callback_data="main_menu")])
    text = utils.tr(lang, "favorites.title")
    if missing:
        text += f"\n\n{utils.tr(lang, 'favorites.missing', count=missing)}"
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
        user = await db.get_or_create_user(callback.from_user.id)
        notice = utils.tr(utils.get_ui_lang(user), "session.favorite_removed")
    else:
        await db.add_favorite(callback.from_user.id, session_id)
        user = await db.get_or_create_user(callback.from_user.id)
        notice = utils.tr(utils.get_ui_lang(user), "session.favorite_added")

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
        user = await db.get_or_create_user(callback.from_user.id)
        await callback.answer(utils.tr(utils.get_ui_lang(user), "session.not_found"), show_alert=True)
        return

    remind_type = callback_data.remind_type
    target_ts = _reminder_target_ts(session, remind_type)
    if target_ts is None:
        user = await db.get_or_create_user(callback.from_user.id)
        await callback.answer(utils.tr(utils.get_ui_lang(user), "session.reminder_create_failed"), show_alert=True)
        return
    if target_ts <= int(time.time()):
        user = await db.get_or_create_user(callback.from_user.id)
        await callback.answer(utils.tr(utils.get_ui_lang(user), "session.reminder_time_passed"), show_alert=True)
        return

    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    labels = {
        "1day": utils.tr(lang, "session.reminder_label_1day"),
        "1hour": utils.tr(lang, "session.reminder_label_1hour"),
        "start": utils.tr(lang, "session.reminder_label_start"),
    }
    existing = {row["remind_type"] for row in await db.get_session_reminders(callback.from_user.id, session_id)}
    if remind_type in existing:
        await db.remove_session_reminder(callback.from_user.id, session_id, remind_type)
        await _render_reminder_menu(
            callback, db, mem, session_id, notice=utils.tr(lang, "session.reminder_removed", label=labels[remind_type])
        )
        return

    await db.add_session_reminder(callback.from_user.id, session_id, remind_type, target_ts)
    await _render_reminder_menu(
        callback, db, mem, session_id, notice=utils.tr(lang, "session.reminder_enabled", label=labels[remind_type])
    )
