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


async def _load_sessions_index(
    db: Database,
    mem: MemoryCache,
    http_session,
) -> dict[str, dict]:
    sessions_by_id: dict[str, dict] = {}
    for start, end in (
        utils.history_window(),
        utils.today_window(),
        utils.week_window(),
        utils.notify_window(),
    ):
        for session in await utils.get_sessions(mem, db, http_session, start, end):
            session_id = session.get("id", "")
            if session_id and session_id not in sessions_by_id:
                sessions_by_id[session_id] = session
    return sessions_by_id


async def _load_events_index(
    db: Database,
    mem: MemoryCache,
    http_session,
    ui_lang: str,
) -> dict[str, dict]:
    sessions = list((await _load_sessions_index(db, mem, http_session)).values())
    return utils.group_sessions_by_event(sessions, ui_lang)


async def _load_session_event_map(
    db: Database,
    mem: MemoryCache,
    http_session,
    ui_lang: str,
) -> dict[str, dict]:
    sessions = list((await _load_sessions_index(db, mem, http_session)).values())
    return utils.map_sessions_to_events(sessions, ui_lang)


async def _migrate_legacy_favorites(
    chat_id: int,
    db: Database,
    session_event_map: dict[str, dict],
) -> None:
    legacy = await db.get_favorites(chat_id)
    for row in legacy:
        event = session_event_map.get(row["session_id"])
        if not event:
            continue
        await db.add_event_favorite(chat_id, event["event_key"], event["title"], event["sort_ts"])


async def _render_reminder_menu(
    callback: CallbackQuery,
    db: Database,
    mem: MemoryCache,
    http_session,
    session_id: str,
    notice: str | None = None,
) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    session, _, _ = await utils.load_session_context(db, mem, http_session, session_id)
    if not session:
        await callback.answer(utils.tr(lang, "session.not_found"), show_alert=True)
        return

    reminders = await db.get_session_reminders(callback.from_user.id, session_id)
    active_types = {row["remind_type"] for row in reminders}
    start_ts = session.get("start", 0)
    title = session.get("name", utils.tr(lang, "generic.session"))
    text = (
        f"{utils.tr(lang, 'session.reminder_title')}\n\n"
        f"<b>{title}</b>\n"
        f"{utils.tr(lang, 'session.start')}: <code>{utils.fmt_datetime(start_ts, user['timezone'], lang)}</code>\n\n"
        f"{utils.tr(lang, 'session.reminder_prompt')}"
    )
    await utils.safe_edit_text(
        callback.message,
        text,
        parse_mode="HTML",
        reply_markup=utils.reminder_menu(session_id, active_types, lang),
    )


async def _render_session(
    callback: CallbackQuery,
    db: Database,
    mem: MemoryCache,
    http_session,
    session_id: str,
    notice: str | None = None,
) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)

    session, broadcasts, live_timings = await utils.load_session_context(db, mem, http_session, session_id)
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

    session_event_map = await _load_session_event_map(db, mem, http_session, lang)
    event = session_event_map.get(session_id)
    event_identity = utils.build_event_identity(session, lang)
    event_key = event["event_key"] if event else event_identity.key
    is_fav = await db.is_event_favorite(callback.from_user.id, event_key)
    is_ignored = await db.is_event_ignored(callback.from_user.id, event_key, int(time.time()))
    await utils.safe_edit_text(
        callback.message,
        card,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=utils.session_actions(session_id, event_key, is_fav, is_ignored, lang),
    )


@router.message(Command("favorites"))
async def cmd_favorites(message: Message, db: Database, mem: MemoryCache, runtime_state) -> None:
    await _show_favorites(message, db, mem, runtime_state.http_session)


@router.callback_query(F.data == "favorites")
async def cb_favorites(callback: CallbackQuery, db: Database, mem: MemoryCache, runtime_state) -> None:
    await callback.answer()
    await _show_favorites(callback, db, mem, runtime_state.http_session)


async def _show_favorites(target: Message | CallbackQuery, db: Database, mem: MemoryCache, http_session) -> None:
    chat_id = target.from_user.id if isinstance(target, CallbackQuery) else target.chat.id
    user = await db.get_or_create_user(chat_id, getattr(getattr(target, "from_user", None), "username", None))
    lang = utils.get_ui_lang(user)
    events_index = await _load_events_index(db, mem, http_session, lang)
    session_event_map = await _load_session_event_map(db, mem, http_session, lang)
    await _migrate_legacy_favorites(chat_id, db, session_event_map)
    favorites = await db.get_event_favorites(chat_id)
    if not favorites:
        text = utils.tr(lang, "favorites.empty")
        if isinstance(target, CallbackQuery):
            await utils.safe_edit_text(target.message, text, parse_mode="HTML", reply_markup=utils.back_to_menu(lang))
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=utils.back_to_menu(lang))
        return

    rows = []
    missing = 0
    for fav in favorites:
        event = events_index.get(fav["event_key"])
        if not event:
            missing += 1
            continue
        rows.append([InlineKeyboardButton(
            text=event["title"][:48],
            callback_data=utils.EventViewCD(event_key=fav["event_key"], source="f").pack(),
        )])

    rows.append([InlineKeyboardButton(text=utils.tr(lang, "menu.back_to_menu"), callback_data="main_menu")])
    text = utils.tr(lang, "favorites.title")
    if missing:
        text += f"\n\n{utils.tr(lang, 'favorites.missing', count=missing)}"
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    if isinstance(target, CallbackQuery):
        await utils.safe_edit_text(target.message, text, parse_mode="HTML", reply_markup=markup)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data == "ignored_events")
async def cb_ignored_events(callback: CallbackQuery, db: Database, mem: MemoryCache, runtime_state) -> None:
    await callback.answer()
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    ignored = await db.get_ignored_events(callback.from_user.id, int(time.time()))
    if not ignored:
        await utils.safe_edit_text(
            callback.message,
            utils.tr(lang, "ignored.empty"),
            parse_mode="HTML",
            reply_markup=utils.back_to_menu(lang),
        )
        return

    events_index = await _load_events_index(db, mem, runtime_state.http_session, lang)
    rows = []
    for item in ignored:
        title = events_index.get(item["event_key"], {}).get("title") or item["title"]
        rows.append([InlineKeyboardButton(
            text=title[:48],
            callback_data=utils.EventViewCD(event_key=item["event_key"], source="i").pack(),
        )])
    rows.append([InlineKeyboardButton(text=utils.tr(lang, "menu.back_to_menu"), callback_data="main_menu")])
    await utils.safe_edit_text(
        callback.message,
        utils.tr(lang, "ignored.title"),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


async def _render_event(
    callback: CallbackQuery,
    db: Database,
    mem: MemoryCache,
    http_session,
    event_key: str,
    source: str = "",
) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    events_index = await _load_events_index(db, mem, http_session, lang)
    event = events_index.get(event_key)
    if not event:
        await callback.answer(utils.tr(lang, "event.not_found"), show_alert=True)
        return

    text = utils.render_event_summary(event, user["timezone"], lang, utils.fmt_time, utils.session_category)
    is_favorite = await db.is_event_favorite(callback.from_user.id, event_key)
    is_ignored = await db.is_event_ignored(callback.from_user.id, event_key, int(time.time()))
    await utils.safe_edit_text(
        callback.message,
        text,
        parse_mode="HTML",
        reply_markup=utils.event_actions(
            event_key,
            is_favorite,
            is_ignored,
            lang,
            "favorites" if source == "f" else "ignored_events" if source == "i" else "main_menu",
            source,
        ),
    )


@router.callback_query(utils.EventViewCD.filter())
async def cb_event_view(
    callback: CallbackQuery,
    callback_data: utils.EventViewCD,
    db: Database,
    mem: MemoryCache,
    runtime_state,
) -> None:
    await callback.answer()
    await _render_event(callback, db, mem, runtime_state.http_session, callback_data.event_key, callback_data.source)


@router.callback_query(F.data.startswith("session:"))
async def cb_session_details(
    callback: CallbackQuery,
    db: Database,
    mem: MemoryCache,
    runtime_state,
) -> None:
    await callback.answer()
    session_id = callback.data.split(":", 1)[1]
    await _render_session(callback, db, mem, runtime_state.http_session, session_id)


@router.callback_query(utils.EventActionCD.filter())
async def cb_event_action(
    callback: CallbackQuery,
    callback_data: utils.EventActionCD,
    db: Database,
    mem: MemoryCache,
    runtime_state,
) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    event_key = callback_data.event_key
    events_index = await _load_events_index(db, mem, runtime_state.http_session, lang)
    event = events_index.get(event_key)
    if not event:
        await callback.answer(utils.tr(lang, "event.not_found"), show_alert=True)
        return

    if callback_data.action == "r":
        await db.remove_event_favorite(callback.from_user.id, event_key)
        notice = utils.tr(lang, "session.favorite_removed")
    elif callback_data.action == "a":
        await db.add_event_favorite(callback.from_user.id, event_key, event["title"], event["sort_ts"])
        notice = utils.tr(lang, "session.favorite_added")
    elif callback_data.action == "i":
        last_end_ts = max(
            int(item.get("start", 0) or 0) + int(item.get("durationMinutes", 0) or 0) * 60
            for item in event["sessions"]
        )
        await db.ignore_event(
            callback.from_user.id,
            event_key,
            event["title"],
            event["sort_ts"],
            last_end_ts + 86_400,
        )
        notice = utils.tr(lang, "ignored.added")
    elif callback_data.action == "u":
        await db.unignore_event(callback.from_user.id, event_key)
        notice = utils.tr(lang, "ignored.removed")
    else:
        return

    is_favorite = await db.is_event_favorite(callback.from_user.id, event_key)
    is_ignored = await db.is_event_ignored(callback.from_user.id, event_key, int(time.time()))
    if callback_data.session_id:
        await utils.safe_edit_reply_markup(
            callback.message,
            reply_markup=utils.session_actions(
                callback_data.session_id,
                event_key,
                is_favorite,
                is_ignored,
                lang,
            ),
        )
        await callback.answer(notice)
        return

    await utils.safe_edit_reply_markup(
        callback.message,
        reply_markup=utils.event_actions(
            event_key,
            is_favorite,
            is_ignored,
            lang,
            "favorites" if callback_data.source == "f" else "ignored_events" if callback_data.source == "i" else "main_menu",
            callback_data.source,
        ),
    )
    await callback.answer(notice)


@router.callback_query(utils.RemindCD.filter())
async def cb_session_remind(
    callback: CallbackQuery,
    callback_data: utils.RemindCD,
    db: Database,
    mem: MemoryCache,
    runtime_state,
) -> None:
    await callback.answer()
    session_id = callback_data.session_id
    if callback_data.action == "menu":
        await _render_reminder_menu(callback, db, mem, runtime_state.http_session, session_id)
        return

    session, _, _ = await utils.load_session_context(db, mem, runtime_state.http_session, session_id)
    if not session:
        return

    remind_type = callback_data.remind_type
    target_ts = _reminder_target_ts(session, remind_type)
    if target_ts is None:
        return
    if target_ts <= int(time.time()):
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
            callback, db, mem, runtime_state.http_session, session_id, notice=utils.tr(lang, "session.reminder_removed", label=labels[remind_type])
        )
        return

    await db.add_session_reminder(callback.from_user.id, session_id, remind_type, target_ts)
    await _render_reminder_menu(
        callback, db, mem, runtime_state.http_session, session_id, notice=utils.tr(lang, "session.reminder_enabled", label=labels[remind_type])
    )
