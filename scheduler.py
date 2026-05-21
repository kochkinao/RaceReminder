"""
Scheduler jobs:

  cache_warmup    — every hour: refresh L1+L2
  notifications   — every hour: send reminders
  weekly_digest   — every Monday: send weekly digest

Optimizations vs naive:
  - One get_all_subscriptions() call for all users (was N calls)
  - One get_all_sent_notifications() call, held in memory set
  - Session index built once: series_id → sessions, class_id → sessions
  - Notifications written in one batch INSERT at end of job
  - One get_sessions() + get_broadcasts() shared across all users
"""
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import pytz
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import utils
from config import NOTIFICATION_OFFSETS, NOTIFICATION_WINDOW
from database import Database
from utils.cache import MemoryCache

log = logging.getLogger(__name__)

type Row = dict[str, Any]


# ── Scheduler factory ─────────────────────────────────────────────────────────

def make_scheduler(bot: Bot, db: Database, mem: MemoryCache) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        lambda: _warmup_job(db, mem),
        trigger="interval", hours=1,
        id="cache_warmup", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _notifications_job(bot, db, mem),
        trigger="interval", hours=1, minutes=5,
        id="notifications", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _weekly_digest_job(bot, db, mem),
        trigger="cron", day_of_week="mon", hour="*", minute=10,
        id="weekly_digest", replace_existing=True,
    )
    return scheduler


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_quiet(user: Row) -> bool:
    if not user.get("quiet_enabled"):
        return False
    try:
        tz = pytz.timezone(user.get("timezone", "UTC"))
    except Exception:
        return False
    h     = datetime.now(tz).hour
    start = user.get("quiet_start", 23)
    end   = user.get("quiet_end", 7)
    return (h >= start or h < end) if start > end else (start <= h < end)


def _build_session_index(
    sessions: list[Row],
) -> tuple[dict[str, list[Row]], dict[str, list[Row]]]:
    """
    Build two indexes once for O(1) per-user lookup:
      series_idx:  series_id  → [session, ...]
      class_idx:   class_id   → [session, ...]
    """
    series_idx: dict[str, list[Row]] = defaultdict(list)
    class_idx:  dict[str, list[Row]] = defaultdict(list)

    for s in sessions:
        for sr in s.get("series", []):
            series_idx[sr["id"]].append(s)
            for vc in sr.get("vehicleClasses", []):
                class_idx[vc["id"]].append(s)

    return dict(series_idx), dict(class_idx)


def _sessions_for_user(
    series_ids: set[str],
    class_ids:  set[str],
    series_idx: dict[str, list[Row]],
    class_idx:  dict[str, list[Row]],
) -> list[Row]:
    seen: dict[str, Row] = {}
    for sid in series_ids:
        for s in series_idx.get(sid, []):
            seen[s["id"]] = s
    for cid in class_ids:
        for s in class_idx.get(cid, []):
            seen[s["id"]] = s
    return sorted(seen.values(), key=lambda s: s.get("start", 0))


async def _send(
    bot:     Bot,
    chat_id: int,
    text:    str,
    session: Row,
    kb:      InlineKeyboardMarkup,
) -> None:
    try:
        await bot.send_message(
            chat_id, text,
            parse_mode="HTML", reply_markup=kb,
            disable_web_page_preview=True,
        )
    except Exception as exc:
        log.error("Send failed → %d: %s", chat_id, exc)
        raise


# ── Warm-up job ───────────────────────────────────────────────────────────────

async def _warmup_job(db: Database, mem: MemoryCache) -> None:
    await utils.warm_up(mem, db)


# ── Notification job ──────────────────────────────────────────────────────────

_FIELD_MAP = {
    "3days": "notify_3days",
    "1day":  "notify_1day",
    "1hour": "notify_1hour",
    "start": "notify_start",
}


def _matched_subscriptions(session: Row, subs: list[Row]) -> list[Row]:
    series_ids = {sr["id"] for sr in session.get("series", [])}
    class_ids = {
        vc["id"]
        for sr in session.get("series", [])
        for vc in sr.get("vehicleClasses", [])
    }
    return [
        sub for sub in subs
        if (sub["type"] == "series" and sub["ref_id"] in series_ids)
        or (sub["type"] == "vehicle_class" and sub["ref_id"] in class_ids)
    ]


def _allows_session_type(session: Row, subs: list[Row]) -> bool:
    category = utils.session_category(session.get("name", ""))
    if category == "race":
        return True

    matched = _matched_subscriptions(session, subs)
    if not matched:
        return False

    if category == "qualifying":
        return any(sub.get("qualifying_notify", sub.get("qual_notify", 1)) for sub in matched)
    if category == "practice":
        return any(sub.get("practice_notify", sub.get("qual_notify", 1)) for sub in matched)
    return True


async def _notifications_job(bot: Bot, db: Database, mem: MemoryCache) -> None:
    log.info("Notification job started")
    t0  = time.monotonic()
    now = int(time.time())

    n_start, n_end = utils.notify_window()

    # ── One API call for all users ────────────────────────────────────────────
    all_sessions   = await utils.get_sessions(mem, db, n_start, n_end)
    all_broadcasts = await utils.get_broadcasts(mem, db, n_start)
    bc_map         = utils.broadcasts_by_session(all_broadcasts)

    # ── One DB call for all users ─────────────────────────────────────────────
    all_users      = await db.get_all_users()
    all_subs       = await db.get_all_subscriptions()        # {chat_id: [rows]}
    sent_set       = await db.get_all_sent_notifications()   # {(chat_id, sid, type)}

    # ── Build session index once ──────────────────────────────────────────────
    series_idx, class_idx = _build_session_index(all_sessions)

    # ── Accumulate new notifications to batch-write ───────────────────────────
    to_send:  list[tuple[int, Row, str, list, list[str]]] = []  # (chat_id, session, type, bc, langs)
    to_mark:  list[tuple[int, str, str]] = []

    for user in all_users:
        if _is_quiet(user):
            continue

        chat_id    = user["chat_id"]
        user_langs = json.loads(user.get("preferred_langs", '["English"]'))
        subs       = all_subs.get(chat_id, [])
        series_ids = {s["ref_id"] for s in subs if s["type"] == "series"}
        class_ids  = {s["ref_id"] for s in subs if s["type"] == "vehicle_class"}

        sessions = _sessions_for_user(series_ids, class_ids, series_idx, class_idx)

        for session in sessions:
            sid      = session.get("id", "")
            start_ts = session.get("start", 0)
            if not start_ts:
                continue

            diff    = start_ts - now

            for notif_type, offset in NOTIFICATION_OFFSETS.items():
                if not user.get(_FIELD_MAP.get(notif_type, ""), 1):
                    continue
                if not (offset - NOTIFICATION_WINDOW <= diff < offset + NOTIFICATION_WINDOW):
                    continue
                if (chat_id, sid, notif_type) in sent_set:
                    continue

                if not _allows_session_type(session, subs):
                    continue

                to_send.append((chat_id, session, notif_type, bc_map.get(sid, []), user_langs))
                to_mark.append((chat_id, sid, notif_type))
                sent_set.add((chat_id, sid, notif_type))  # prevent duplicates within same run

    log.info("Sending %d notifications", len(to_send))

    # ── Send all notifications ────────────────────────────────────────────────
    successfully_marked: list[tuple[int, str, str]] = []

    for chat_id, session, notif_type, broadcasts, user_langs in to_send:
        # Find user tz for formatting
        user = next((u for u in all_users if u["chat_id"] == chat_id), None)
        if not user:
            continue

        text = utils.notification_text(
            session, broadcasts, [],
            user_tz=user["timezone"],
            user_langs=user_langs,
            notif_type=notif_type,
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="❤️ В избранное",
                callback_data=utils.FavCD(
                    action="add", session_id=session.get("id", "")
                ).pack(),
            ),
            InlineKeyboardButton(text="📆 Неделя", callback_data="week"),
        ]])

        try:
            await _send(bot, chat_id, text, session, kb)
            successfully_marked.append((chat_id, session.get("id", ""), notif_type))
            log.info("Sent %s → %d (%s)", notif_type, chat_id, session.get("id","")[:8])
        except Exception:
            pass  # logged inside _send

    # ── Batch-write sent notifications ────────────────────────────────────────
    await db.mark_notified_batch(successfully_marked)

    elapsed = time.monotonic() - t0
    log.info(
        "Notification job done in %.2fs. Sent: %d/%d",
        elapsed, len(successfully_marked), len(to_send),
    )


# ── Weekly digest job ─────────────────────────────────────────────────────────

async def _weekly_digest_job(bot: Bot, db: Database, mem: MemoryCache) -> None:
    log.info("Weekly digest job started")
    now_utc        = datetime.now(timezone.utc)
    w_start, w_end = utils.week_window()
    label          = utils.week_label(w_start, w_end)

    # ── One API call for all users ────────────────────────────────────────────
    all_sessions   = await utils.get_sessions(mem, db, w_start, w_end)
    all_broadcasts = await utils.get_broadcasts(mem, db, w_start)
    bc_map         = utils.broadcasts_by_session(all_broadcasts)

    # ── One DB call for all users ─────────────────────────────────────────────
    all_users = await db.get_all_users()
    all_subs  = await db.get_all_subscriptions()
    sent_set  = await db.get_all_sent_notifications()

    series_idx, class_idx = _build_session_index(all_sessions)

    successfully_marked: list[tuple[int, str, str]] = []

    for user in all_users:
        if not user.get("digest_enabled"):
            continue

        try:
            tz        = pytz.timezone(user["timezone"])
            now_local = now_utc.astimezone(tz)
            dh, _     = map(int, user["digest_time"].split(":"))
            if now_local.hour != dh:
                continue
        except Exception:
            continue

        chat_id  = user["chat_id"]
        week_key = f"digest:{now_local.strftime('%Y-W%V')}"

        if (chat_id, "weekly", week_key) in sent_set:
            continue

        subs       = all_subs.get(chat_id, [])
        series_ids = {s["ref_id"] for s in subs if s["type"] == "series"}
        class_ids  = {s["ref_id"] for s in subs if s["type"] == "vehicle_class"}
        sessions   = _sessions_for_user(series_ids, class_ids, series_idx, class_idx)
        langs      = json.loads(user.get("preferred_langs", '["English"]'))
        show_no_bc = bool(user.get("show_no_broadcast", 1))

        try:
            messages = utils.build_digest(
                sessions, bc_map, {},
                user_tz=user["timezone"],
                user_langs=langs,
                show_no_bc=show_no_bc,
                header=f"📆 <b>Гонки на неделю</b> — {label}",
            )
            reply_markup = (
                utils.week_pager(0, len(messages))
                if len(messages) > 1
                else utils.back_to_menu()
            )
            await bot.send_message(
                chat_id, messages[0],
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=reply_markup,
            )

            successfully_marked.append((chat_id, "weekly", week_key))
            sent_set.add((chat_id, "weekly", week_key))
            log.info("Weekly digest → %d", chat_id)
        except Exception as exc:
            log.error("Weekly digest failed %d: %s", chat_id, exc)

    await db.mark_notified_batch(successfully_marked)
    log.info("Weekly digest job done. Sent: %d", len(successfully_marked))
