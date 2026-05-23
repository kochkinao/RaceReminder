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


def _subs_ids_from_subs(subs: list[dict]) -> tuple[set[str], set[str]]:
    return (
        {s["ref_id"] for s in subs if s["type"] == "series"},
        {s["ref_id"] for s in subs if s["type"] == "vehicle_class"},
    )


def _subscription_matches_session(session: dict, sub: dict) -> bool:
    if sub["type"] == "series":
        return any(series.get("id") == sub["ref_id"] for series in session.get("series", []))
    if sub["type"] == "vehicle_class":
        return any(
            vehicle_class.get("id") == sub["ref_id"]
            for series in session.get("series", [])
            for vehicle_class in series.get("vehicleClasses", [])
        )
    return False


def _matched_subscriptions(session: dict, subs: list[dict]) -> list[dict]:
    return [sub for sub in subs if _subscription_matches_session(session, sub)]


def _allows_session_type(session: dict, subs: list[dict]) -> bool:
    category = utils.session_category(session.get("name", ""))
    if category == "race":
        return True
    if not subs:
        return False
    if category == "qualifying":
        return any(sub.get("qualifying_notify", sub.get("qual_notify", 1)) for sub in subs)
    if category == "practice":
        return any(sub.get("practice_notify", sub.get("qual_notify", 1)) for sub in subs)
    return True


def _filter_digest_sessions(
    sessions: list[dict],
    subs: list[dict],
    user: dict,
    selected_sub: dict | None = None,
) -> list[dict]:
    result: list[dict] = []
    for session in sessions:
        category = utils.session_category(session.get("name", ""))
        if category == "qualifying" and not user.get("show_qualifying", 1):
            continue
        if category == "practice" and not user.get("show_practice", 1):
            continue
        matched = _matched_subscriptions(session, subs)
        if selected_sub:
            matched = [sub for sub in matched if sub["type"] == selected_sub["type"] and sub["ref_id"] == selected_sub["ref_id"]]
        if not matched:
            continue
        if not _allows_session_type(session, matched):
            continue
        result.append(session)
    return result


def _resolve_subscription(subs: list[dict], scope: str, ref_id: str) -> dict | None:
    if scope not in {"series", "vehicle_class"} or not ref_id:
        return None
    return next(
        (
            sub for sub in subs
            if sub["type"] == scope and sub["ref_id"].startswith(ref_id)
        ),
        None,
    )


def _digest_summary_text(
    kind: str,
    header: str,
    sessions: list[dict],
    subs: list[dict],
    lang: str,
) -> str:
    series_count = sum(1 for sub in subs if sub["type"] == "series")
    class_count = sum(1 for sub in subs if sub["type"] == "vehicle_class")
    label = utils.tr(lang, "digest.period_today" if kind == "today" else "digest.period_week")
    return utils.tr(
        lang,
        "digest.summary",
        header=header,
        count=len(sessions),
        period=label,
        series_count=series_count,
        class_count=class_count,
    )


def _selected_digest_header(header: str, sub: dict | None, lang: str) -> str:
    if not sub:
        return header
    prefix = "🏎️" if sub["type"] == "series" else "🏷️"
    return f"{header}\n{utils.tr(lang, 'digest.filter')}: {prefix} <b>{sub['ref_name']}</b>"


def _is_empty_digest(messages: list[str], header: str, lang: str) -> bool:
    empty_text = (header + "\n\n" if header else "") + (
        "😴 No sessions found for your subscriptions." if lang == "en" else "😴 Нет гонок по вашим подпискам."
    )
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
    ui_lang: str,
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
            ui_lang=ui_lang,
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
        pages.append(header + "\n\n" + utils.tr(ui_lang, "digest.no_filter_results"))
    return pages


def _history_filter_label(
    filter_type: str,
    ref_id: str,
    subs: list[dict],
    lang: str,
) -> str:
    if filter_type in {"all", ""}:
        return utils.tr(lang, "digest.filter_all")
    if filter_type == "race":
        return utils.tr(lang, "digest.filter_race")
    if filter_type == "qualifying":
        return utils.tr(lang, "digest.filter_qualifying")
    if filter_type == "practice":
        return utils.tr(lang, "digest.filter_practice")

    for sub in subs:
        if sub["ref_id"] == ref_id:
            key = "digest.filter_series" if filter_type == "series" else "digest.filter_class"
            return utils.tr(lang, key, name=sub["ref_name"])
    return filter_type


async def _send_or_edit_digest(
    target: Message,
    *,
    text: str,
    reply_markup: InlineKeyboardMarkup | None,
    as_edit: bool,
) -> None:
    if as_edit:
        await utils.safe_edit_text(
            target,
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=reply_markup,
        )
        return
    await target.answer(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=reply_markup,
    )


async def _send_digest_empty_state(
    target: Message,
    *,
    text: str,
    lang: str,
    as_edit: bool,
) -> None:
    await _send_or_edit_digest(
        target,
        text=text,
        reply_markup=utils.empty_state_menu(lang),
        as_edit=as_edit,
    )


async def _render_digest(
    target: Message,
    db: Database,
    *,
    kind: str,
    sessions: list[dict],
    bc_map: dict[str, list[dict]],
    user: dict,
    subs: list[dict],
    header: str,
    page: int = 0,
    pick_page: int = 0,
    scope: str = "all",
    ref_id: str = "",
    action: str = "view",
    as_edit: bool = False,
) -> None:
    selected_sub = _resolve_subscription(subs, scope, ref_id)
    user_langs = json.loads(user.get("preferred_langs", '["English"]'))
    ui_lang = utils.get_ui_lang(user)

    if len(subs) <= 1 and not selected_sub and subs:
        selected_sub = subs[0]

    filtered_sessions = _filter_digest_sessions(sessions, subs, user, selected_sub if scope != "all" or len(subs) <= 1 else None)
    view_header = _selected_digest_header(header, selected_sub if scope != "all" or len(subs) <= 1 else None, ui_lang)

    if action == "pick" and len(subs) > 1:
        await _send_or_edit_digest(
            target,
            text=_digest_summary_text(kind, header, filtered_sessions, subs, ui_lang),
            reply_markup=utils.digest_pick_menu(kind, subs, page, lang=ui_lang),
            as_edit=as_edit,
        )
        return

    messages = utils.build_digest(
        filtered_sessions,
        bc_map,
        {},
        user_tz=user["timezone"],
        user_langs=user_langs,
        show_no_bc=bool(user.get("show_no_broadcast", 1)),
        header=view_header,
        ui_lang=ui_lang,
    )

    if _is_empty_digest(messages, view_header, ui_lang):
        kb = utils.digest_view_menu(
            kind,
            0,
            1,
            selected_sub=selected_sub if scope != "all" or len(subs) <= 1 else None,
            user=user,
            pick_page=pick_page,
            allow_pick=len(subs) > 1,
            lang=ui_lang,
        )
        await _send_or_edit_digest(
            target,
            text=messages[0],
            reply_markup=kb,
            as_edit=as_edit,
        )
        return

    safe_page = max(0, min(page, len(messages) - 1))
    kb = utils.digest_view_menu(
        kind,
        safe_page,
        len(messages),
        selected_sub=selected_sub if scope != "all" or len(subs) <= 1 else None,
        user=user,
        pick_page=pick_page,
        allow_pick=len(subs) > 1,
        lang=ui_lang,
    )
    await _send_or_edit_digest(
        target,
        text=messages[safe_page],
        reply_markup=kb,
        as_edit=as_edit,
    )


# ── /today ────────────────────────────────────────────────────────────────────

@router.message(Command("today"))
async def cmd_today(message: Message, db: Database, mem: MemoryCache, runtime_state) -> None:
    await _handle_today(message, db, mem, runtime_state.http_session)

@router.callback_query(F.data == "today")
async def cb_today(callback: CallbackQuery, db: Database, mem: MemoryCache, runtime_state) -> None:
    await callback.answer()
    await _handle_today(
        callback.message, db, mem, runtime_state.http_session, chat_id=callback.from_user.id, as_edit=True
    )


@router.callback_query(F.data.startswith("today_page:"))
async def cb_today_page(callback: CallbackQuery, db: Database, mem: MemoryCache, runtime_state) -> None:
    await callback.answer()
    page = int(callback.data.split(":", 1)[1])
    await _handle_today(
        callback.message,
        db,
        mem,
        runtime_state.http_session,
        page=page,
        action="view",
        chat_id=callback.from_user.id,
        as_edit=True,
    )


async def _toggle_digest_subscription(
    callback: CallbackQuery,
    callback_data: utils.DigestViewCD,
    db: Database,
    mem: MemoryCache,
    http_session,
) -> None:
    if callback_data.field not in {"show_qualifying", "show_practice"}:
        return

    user = await db.get_or_create_user(callback.from_user.id)
    new_value = 0 if user.get(callback_data.field, 1) else 1
    await db.update_user(callback.from_user.id, **{callback_data.field: new_value})

    if callback_data.kind == "today":
        await _handle_today(
            callback.message,
            db,
            mem,
            http_session,
            page=callback_data.page,
            pick_page=callback_data.pick_page,
            scope=callback_data.scope,
            ref_id=callback_data.ref_id,
            action="view",
            chat_id=callback.from_user.id,
            as_edit=True,
        )
    else:
        await _handle_week(
            callback.message,
            db,
            mem,
            http_session,
            page=callback_data.page,
            pick_page=callback_data.pick_page,
            scope=callback_data.scope,
            ref_id=callback_data.ref_id,
            action="view",
            chat_id=callback.from_user.id,
            as_edit=True,
        )


@router.callback_query(utils.DigestViewCD.filter(F.kind == "today"))
async def cb_today_digest(
    callback: CallbackQuery,
    callback_data: utils.DigestViewCD,
    db: Database,
    mem: MemoryCache,
    runtime_state,
) -> None:
    await callback.answer()
    if callback_data.action == "toggle":
        await _toggle_digest_subscription(callback, callback_data, db, mem, runtime_state.http_session)
        return
    await _handle_today(
        callback.message,
        db,
        mem,
        runtime_state.http_session,
        page=callback_data.page,
        pick_page=callback_data.pick_page,
        scope=callback_data.scope,
        ref_id=callback_data.ref_id,
        action=callback_data.action,
        chat_id=callback.from_user.id,
        as_edit=True,
    )


async def _handle_today(
    target: Message,
    db: Database,
    mem: MemoryCache,
    http_session,
    page: int = 0,
    pick_page: int = 0,
    scope: str = "all",
    ref_id: str = "",
    action: str = "pick",
    chat_id: int | None = None,
    as_edit: bool = False,
) -> None:
    from datetime import datetime, timezone
    chat_id = chat_id or target.chat.id
    user          = await db.get_or_create_user(chat_id)
    t_start, t_end = utils.today_window()
    subs = await db.get_subscriptions(chat_id)
    series_ids, class_ids = _subs_ids_from_subs(subs)
    if not subs:
        await _send_digest_empty_state(
            target,
            text=utils.tr(utils.get_ui_lang(user), "digest.no_subscriptions_today"),
            lang=utils.get_ui_lang(user),
            as_edit=as_edit,
        )
        return

    all_sessions   = await utils.get_sessions(mem, db, http_session, t_start, t_end)
    all_broadcasts = await utils.get_broadcasts(mem, db, http_session, t_start)
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
    header = f"{utils.tr(utils.get_ui_lang(user), 'digest.today_header')} — {date_label}"
    await _render_digest(
        target,
        db,
        kind="today",
        sessions=sessions,
        bc_map=bc_map,
        user=user,
        subs=subs,
        header=header,
        page=page,
        pick_page=pick_page,
        scope=scope,
        ref_id=ref_id,
        action=action,
        as_edit=as_edit,
    )


# ── /week ─────────────────────────────────────────────────────────────────────

@router.message(Command("week"))
async def cmd_week(message: Message, db: Database, mem: MemoryCache, runtime_state) -> None:
    await _handle_week(message, db, mem, runtime_state.http_session)

@router.callback_query(F.data == "week")
async def cb_week(callback: CallbackQuery, db: Database, mem: MemoryCache, runtime_state) -> None:
    await callback.answer()
    await _handle_week(
        callback.message, db, mem, runtime_state.http_session, chat_id=callback.from_user.id, as_edit=True
    )


@router.callback_query(F.data.startswith("week_page:"))
async def cb_week_page(callback: CallbackQuery, db: Database, mem: MemoryCache, runtime_state) -> None:
    await callback.answer()
    page = int(callback.data.split(":", 1)[1])
    await _handle_week(
        callback.message,
        db,
        mem,
        runtime_state.http_session,
        page=page,
        action="view",
        chat_id=callback.from_user.id,
        as_edit=True,
    )


@router.callback_query(utils.DigestViewCD.filter(F.kind == "week"))
async def cb_week_digest(
    callback: CallbackQuery,
    callback_data: utils.DigestViewCD,
    db: Database,
    mem: MemoryCache,
    runtime_state,
) -> None:
    await callback.answer()
    if callback_data.action == "toggle":
        await _toggle_digest_subscription(callback, callback_data, db, mem, runtime_state.http_session)
        return
    await _handle_week(
        callback.message,
        db,
        mem,
        runtime_state.http_session,
        page=callback_data.page,
        pick_page=callback_data.pick_page,
        scope=callback_data.scope,
        ref_id=callback_data.ref_id,
        action=callback_data.action,
        chat_id=callback.from_user.id,
        as_edit=True,
    )


async def _handle_week(
    target: Message,
    db: Database,
    mem: MemoryCache,
    http_session,
    page: int = 0,
    pick_page: int = 0,
    scope: str = "all",
    ref_id: str = "",
    action: str = "pick",
    chat_id: int | None = None,
    as_edit: bool = False,
) -> None:
    chat_id = chat_id or target.chat.id
    user = await db.get_or_create_user(chat_id)
    w_start, w_end = utils.week_window()
    subs = await db.get_subscriptions(chat_id)
    series_ids, class_ids = _subs_ids_from_subs(subs)
    if not subs:
        await _send_digest_empty_state(
            target,
            text=utils.tr(utils.get_ui_lang(user), "digest.no_subscriptions_week"),
            lang=utils.get_ui_lang(user),
            as_edit=as_edit,
        )
        return

    all_sessions   = await utils.get_sessions(mem, db, http_session, w_start, w_end)
    all_broadcasts = await utils.get_broadcasts(mem, db, http_session, w_start)
    sessions = utils.filter_sessions_for_user(all_sessions, series_ids, class_ids)
    bc_map   = utils.broadcasts_by_session(all_broadcasts)
    label    = utils.week_label(w_start, w_end)

    header = f"{utils.tr(utils.get_ui_lang(user), 'digest.week_header')} — {label}"
    await _render_digest(
        target,
        db,
        kind="week",
        sessions=sessions,
        bc_map=bc_map,
        user=user,
        subs=subs,
        header=header,
        page=page,
        pick_page=pick_page,
        scope=scope,
        ref_id=ref_id,
        action=action,
        as_edit=as_edit,
    )


# ── /history ──────────────────────────────────────────────────────────────────

@router.message(Command("history"))
async def cmd_history(message: Message, db: Database, mem: MemoryCache, runtime_state) -> None:
    await _render_history(message, db, mem, runtime_state.http_session)


@router.callback_query(F.data == "history")
async def cb_history(callback: CallbackQuery, db: Database, mem: MemoryCache, runtime_state) -> None:
    await callback.answer()
    await _render_history(
        callback.message, db, mem, runtime_state.http_session, chat_id=callback.from_user.id, as_edit=True
    )


@router.callback_query(utils.HistoryViewCD.filter())
async def cb_history_view(
    callback: CallbackQuery,
    callback_data: utils.HistoryViewCD,
    db: Database,
    mem: MemoryCache,
    runtime_state,
) -> None:
    await callback.answer()
    await _render_history(
        callback.message,
        db,
        mem,
        runtime_state.http_session,
        filter_type=callback_data.filter_type,
        ref_id=callback_data.ref_id,
        page=callback_data.page,
        chat_id=callback.from_user.id,
        as_edit=True,
    )


@router.callback_query(utils.HistoryPickCD.filter())
async def cb_history_pick(
    callback: CallbackQuery,
    callback_data: utils.HistoryPickCD,
    db: Database,
) -> None:
    await callback.answer()
    subs = await db.get_subscriptions(callback.from_user.id)
    items = [sub for sub in subs if sub["type"] == callback_data.kind]
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    title = utils.tr(lang, "digest.pick_series_title" if callback_data.kind == "series" else "digest.pick_class_title")
    if not items:
        return
    await utils.safe_edit_text(
        callback.message,
        title,
        parse_mode="HTML",
        reply_markup=utils.history_pick_menu(callback_data.kind, items, callback_data.page, lang=lang),
    )


async def _render_history(
    target: Message,
    db: Database,
    mem: MemoryCache,
    http_session,
    filter_type: str = "all",
    ref_id: str = "",
    page: int = 0,
    chat_id: int | None = None,
    as_edit: bool = False,
) -> None:
    chat_id = chat_id or target.chat.id
    user = await db.get_or_create_user(chat_id)
    lang = utils.get_ui_lang(user)
    h_start, h_end = utils.history_window()
    subs = await db.get_subscriptions(chat_id)
    series_ids, class_ids = _subs_ids_from_subs(subs)
    if not subs:
        if as_edit:
            await utils.safe_edit_text(
                target,
                utils.tr(lang, "digest.no_subscriptions_history"),
                parse_mode="HTML",
                reply_markup=utils.empty_state_menu(lang),
            )
        else:
            await target.answer(
                utils.tr(lang, "digest.no_subscriptions_history"),
                parse_mode="HTML",
                reply_markup=utils.empty_state_menu(lang),
            )
        return

    all_sessions = await utils.get_sessions(mem, db, http_session, h_start, h_end)
    all_broadcasts = await utils.get_broadcasts(mem, db, http_session, h_start)
    sessions = utils.filter_sessions_for_user(all_sessions, series_ids, class_ids)
    sessions = sorted(sessions, key=lambda session: session.get("start", 0), reverse=True)
    sessions = _history_filter_sessions(sessions, filter_type, ref_id)
    bc_map = utils.broadcasts_by_session(all_broadcasts)
    langs = json.loads(user.get("preferred_langs", '["English"]'))

    label = _history_filter_label(filter_type, ref_id, subs, lang)
    header = f"{utils.tr(lang, 'digest.history_header')}\n{utils.tr(lang, 'digest.history_period')}\n{utils.tr(lang, 'digest.history_filter_label', label=label)}"
    pages = _history_pages(sessions, bc_map, user["timezone"], langs, header, lang)
    safe_page = max(0, min(page, len(pages) - 1))
    kb = utils.history_filter_menu(filter_type, ref_id, safe_page, len(pages), lang=lang)

    if as_edit:
        await utils.safe_edit_text(
            target,
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

