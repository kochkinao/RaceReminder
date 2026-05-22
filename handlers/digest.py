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
_TODAY_HEADER = "📅 <b>Мой гоночный день</b>"
_WEEK_HEADER = "📆 <b>Моя гоночная неделя</b>"
_HISTORY_HEADER = "📖 <b>История по подпискам</b>"


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


def _history_filter_sessions(
    sessions: list[dict],
    filter_type: str,
    ref_id: str = "",
) -> list[dict]:
    if filter_type in {"all", ""}:
        return sessions

    if filter_type in {"race", "qualifying", "practice"}:
        return [
            session for session in sessions
            if utils.session_category(session.get("name", "")) == filter_type
        ]

    if filter_type == "series":
        return [
            session for session in sessions
            if any(series.get("id") == ref_id for series in session.get("series", []))
        ]

    if filter_type == "vehicle_class":
        return [
            session for session in sessions
            if any(
                vehicle_class.get("id") == ref_id
                for series in session.get("series", [])
                for vehicle_class in series.get("vehicleClasses", [])
            )
        ]

    return sessions


def _history_pages(
    sessions: list[dict],
    bc_map: dict[str, list[dict]],
    user_tz: str,
    user_langs: list[str],
    header: str,
) -> list[str]:
    pages: list[str] = []
    current = header + "\n"

    for session in sessions:
        card = utils.session_card(
            session,
            broadcasts=bc_map.get(session.get("id", ""), []),
            live_timings=[],
            user_tz=user_tz,
            user_langs=user_langs,
            compact=True,
        )
        if not card:
            continue
        entry = "\n" + "─" * 30 + "\n" + card
        if len(current) + len(entry) > 3800:
            pages.append(current)
            current = header + entry
        else:
            current += entry

    if current.strip():
        pages.append(current)
    if not pages:
        pages.append(header + "\n\n😴 Ничего не найдено по выбранному фильтру.")
    return pages


def _history_filter_label(
    filter_type: str,
    ref_id: str,
    subs: list[dict],
) -> str:
    if filter_type in {"all", ""}:
        return "все сессии"
    if filter_type == "race":
        return "только гонки"
    if filter_type == "qualifying":
        return "только квалификации"
    if filter_type == "practice":
        return "только практики"

    for sub in subs:
        if sub["ref_id"] == ref_id:
            prefix = "серия" if filter_type == "series" else "класс"
            return f"{prefix}: {sub['ref_name']}"
    return filter_type


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
    await _render_history(message, db, mem)


@router.callback_query(F.data == "history")
async def cb_history(callback: CallbackQuery, db: Database, mem: MemoryCache) -> None:
    await _render_history(callback.message, db, mem, as_edit=True)
    await callback.answer()


@router.callback_query(utils.HistoryViewCD.filter())
async def cb_history_view(
    callback: CallbackQuery,
    callback_data: utils.HistoryViewCD,
    db: Database,
    mem: MemoryCache,
) -> None:
    await _render_history(
        callback.message,
        db,
        mem,
        filter_type=callback_data.filter_type,
        ref_id=callback_data.ref_id,
        page=callback_data.page,
        as_edit=True,
    )
    await callback.answer()


@router.callback_query(utils.HistoryPickCD.filter())
async def cb_history_pick(
    callback: CallbackQuery,
    callback_data: utils.HistoryPickCD,
    db: Database,
) -> None:
    subs = await db.get_subscriptions(callback.from_user.id)
    items = [sub for sub in subs if sub["type"] == callback_data.kind]
    title = "🏎️ <b>Фильтр по серии</b>" if callback_data.kind == "series" else "🏷️ <b>Фильтр по классу</b>"
    if not items:
        await callback.answer("Нет подходящих подписок для фильтра.", show_alert=True)
        return
    await callback.message.edit_text(
        title + "\n\nВыберите фильтр:",
        parse_mode="HTML",
        reply_markup=utils.history_pick_menu(callback_data.kind, items, callback_data.page),
    )
    await callback.answer()


async def _render_history(
    target: Message,
    db: Database,
    mem: MemoryCache,
    filter_type: str = "all",
    ref_id: str = "",
    page: int = 0,
    as_edit: bool = False,
) -> None:
    user = await db.get_user(target.chat.id)
    h_start, h_end = utils.history_window()
    series_ids, class_ids = await _subs_ids(db, target.chat.id)
    subs = await db.get_subscriptions(target.chat.id)

    all_sessions = await utils.get_sessions(mem, db, h_start, h_end)
    all_broadcasts = await utils.get_broadcasts(mem, db, h_start)
    sessions = utils.filter_sessions_for_user(all_sessions, series_ids, class_ids)
    sessions = sorted(sessions, key=lambda session: session.get("start", 0), reverse=True)
    sessions = _history_filter_sessions(sessions, filter_type, ref_id)
    bc_map = utils.broadcasts_by_session(all_broadcasts)
    langs = json.loads(user.get("preferred_langs", '["English"]'))

    label = _history_filter_label(filter_type, ref_id, subs)
    header = f"{_HISTORY_HEADER}\nПериод: последние <b>7 дней</b>\nФильтр: <b>{label}</b>"
    pages = _history_pages(sessions, bc_map, user["timezone"], langs, header)
    safe_page = max(0, min(page, len(pages) - 1))
    kb = utils.history_filter_menu(filter_type, ref_id, safe_page, len(pages))

    if as_edit:
        await target.edit_text(
            pages[safe_page],
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=kb,
        )
        return

    await target.answer(
        pages[safe_page],
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=kb,
    )

