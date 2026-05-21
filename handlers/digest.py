import json
import logging

import pytz
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import utils
from database import Database
from utils.cache import MemoryCache

log = logging.getLogger(__name__)
router = Router()
_TODAY_HEADER = "📅 <b>Гонки на сегодня</b>"
_WEEK_HEADER = "📆 <b>Гонки на неделю</b>"


async def _subs_ids(db: Database, chat_id: int) -> tuple[set[str], set[str]]:
    subs = await db.get_subscriptions(chat_id)
    return (
        {s["ref_id"] for s in subs if s["type"] == "series"},
        {s["ref_id"] for s in subs if s["type"] == "vehicle_class"},
    )


def _paginate_digest(
    messages: list[str],
    page: int,
    kind: str,
) -> tuple[str, InlineKeyboardMarkup | None]:
    total = len(messages)
    safe_page = max(0, min(page, total - 1))
    if total > 1:
        kb = utils.week_pager(safe_page, total) if kind == "week" else utils.today_pager(safe_page, total)
    else:
        kb = utils.back_to_menu()
    return messages[safe_page], kb


def _is_empty_digest(messages: list[str], header: str) -> bool:
    empty_text = (header + "\n\n" if header else "") + "😴 Нет гонок по вашим подпискам."
    return len(messages) == 1 and messages[0] == empty_text


# ── /today ────────────────────────────────────────────────────────────────────

@router.message(Command("today"))
async def cmd_today(message: Message, db: Database, mem: MemoryCache) -> None:
    await _handle_today(message, db, mem)

@router.callback_query(F.data == "today")
async def cb_today(callback: CallbackQuery, db: Database, mem: MemoryCache) -> None:
    await callback.answer("Загружаю...")
    await _handle_today(callback.message, db, mem, as_edit=True)


@router.callback_query(F.data.startswith("today_page:"))
async def cb_today_page(callback: CallbackQuery, db: Database, mem: MemoryCache) -> None:
    await callback.answer()
    page = int(callback.data.split(":", 1)[1])
    await _handle_today(callback.message, db, mem, page=page, as_edit=True)


async def _handle_today(
    target: Message,
    db: Database,
    mem: MemoryCache,
    page: int = 0,
    as_edit: bool = False,
) -> None:
    from datetime import datetime, timezone
    user          = await db.get_user(target.chat.id)
    t_start, t_end = utils.today_window()
    series_ids, class_ids = await _subs_ids(db, target.chat.id)

    all_sessions   = await utils.get_sessions(mem, db, t_start, t_end)
    all_broadcasts = await utils.get_broadcasts(mem, db, t_start)
    sessions = utils.filter_sessions_for_user(all_sessions, series_ids, class_ids)
    bc_map   = utils.broadcasts_by_session(all_broadcasts)

    tz        = pytz.timezone(user["timezone"])
    now_local = datetime.now(tz)

    # Narrow the wide cache window to sessions actually starting today in the
    # user's local timezone.  today_window() returns ~52h to cover UTC-14…UTC+14;
    # without this filter a Moscow user at 23:00 would see tomorrow's races.
    today_local = now_local.date()
    sessions = [
        s for s in sessions
        if s.get("start") and
           datetime.fromtimestamp(s["start"], tz=timezone.utc).astimezone(tz).date() == today_local
    ]

    date_label = now_local.strftime("%d %B %Y")
    header = f"{_TODAY_HEADER} — {date_label}"
    messages = utils.build_digest(
        sessions, bc_map, {},
        user_tz=user["timezone"],
        user_langs=json.loads(user.get("preferred_langs", '["English"]')),
        show_no_bc=bool(user.get("show_no_broadcast", 1)),
        header=header,
    )

    if _is_empty_digest(messages, header):
        text = messages[0]
        if as_edit:
            await target.edit_text(
                text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return
        await target.answer(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return

    text, kb = _paginate_digest(messages, page, "today")
    if as_edit:
        await target.edit_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=kb,
        )
        return

    await target.answer(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=kb,
    )


# ── /week ─────────────────────────────────────────────────────────────────────

@router.message(Command("week"))
async def cmd_week(message: Message, db: Database, mem: MemoryCache) -> None:
    await _handle_week(message, db, mem)

@router.callback_query(F.data == "week")
async def cb_week(callback: CallbackQuery, db: Database, mem: MemoryCache) -> None:
    await callback.answer("Загружаю...")
    await _handle_week(callback.message, db, mem, as_edit=True)


@router.callback_query(F.data.startswith("week_page:"))
async def cb_week_page(callback: CallbackQuery, db: Database, mem: MemoryCache) -> None:
    await callback.answer()
    page = int(callback.data.split(":", 1)[1])
    await _handle_week(callback.message, db, mem, page=page, as_edit=True)


async def _handle_week(
    target: Message,
    db: Database,
    mem: MemoryCache,
    page: int = 0,
    as_edit: bool = False,
) -> None:
    user = await db.get_user(target.chat.id)
    w_start, w_end = utils.week_window()
    series_ids, class_ids = await _subs_ids(db, target.chat.id)

    all_sessions   = await utils.get_sessions(mem, db, w_start, w_end)
    all_broadcasts = await utils.get_broadcasts(mem, db, w_start)
    sessions = utils.filter_sessions_for_user(all_sessions, series_ids, class_ids)
    bc_map   = utils.broadcasts_by_session(all_broadcasts)
    langs    = json.loads(user.get("preferred_langs", '["English"]'))
    label    = utils.week_label(w_start, w_end)

    header = f"{_WEEK_HEADER} — {label}"
    messages = utils.build_digest(
        sessions, bc_map, {},
        user_tz=user["timezone"],
        user_langs=langs,
        show_no_bc=bool(user.get("show_no_broadcast", 1)),
        header=header,
    )

    if _is_empty_digest(messages, header):
        text = messages[0]
        if as_edit:
            await target.edit_text(
                text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return
        await target.answer(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return

    text, kb = _paginate_digest(messages, page, "week")

    if as_edit:
        await target.edit_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=kb,
        )
        return

    await target.answer(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=kb,
    )


# ── /history ──────────────────────────────────────────────────────────────────

@router.message(Command("history"))
async def cmd_history(message: Message, db: Database, mem: MemoryCache) -> None:
    user = await db.get_user(message.chat.id)
    h_start, h_end = utils.history_window()
    series_ids, class_ids = await _subs_ids(db, message.chat.id)

    all_sessions   = await utils.get_sessions(mem, db, h_start, h_end)
    all_broadcasts = await utils.get_broadcasts(mem, db, h_start)
    sessions = utils.filter_sessions_for_user(all_sessions, series_ids, class_ids)
    bc_map   = utils.broadcasts_by_session(all_broadcasts)
    langs    = json.loads(user.get("preferred_langs", '["English"]'))

    if not sessions:
        await message.answer("📭 Нет прошедших гонок за последние 7 дней.")
        return

    await message.answer("📖 <b>Прошедшие гонки (7 дней)</b>", parse_mode="HTML")
    for s in sessions[-10:]:
        card = utils.session_card(
            s, bc_map.get(s.get("id", ""), []), [],
            user_tz=user["timezone"], user_langs=langs, compact=True,
        )
        if card:
            await message.answer(card, parse_mode="HTML", disable_web_page_preview=True)

