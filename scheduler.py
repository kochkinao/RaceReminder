"""
Scheduler jobs:
  cache_warmup    — каждый час :00  — прогрев L1+L2
  notifications   — каждый час :05  — уведомления о гонках
  weekly_digest   — каждый пн  :10  — еженедельный дайджест
  db_cleanup      — каждое вс  04:00 — sent_notifications > 30 дней

Оптимизации:
  - Один get_all_subscriptions + get_all_sent_notifications (batch)
  - Session index built once → O(1) per-user lookup
  - Batch INSERT sent_notifications в конце job'а
  - TelegramForbiddenError → user deactivation
  - misfire_grace_time: job запустится даже если опоздал на 10 мин
"""
import asyncio
import json
import logging
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database import Database
from utils.cache import MemoryCache
from utils.metrics import Metrics
from config import (
    NOTIFICATION_OFFSETS,
    NOTIFICATION_WINDOW,
    SCHEDULER_MISFIRE_GRACE,
    TELEGRAM_SEND_DELAY,
)

import utils
from utils.windows import week_window

log = logging.getLogger(__name__)

Row = dict


def make_scheduler(
    bot: Bot, db: Database, mem: MemoryCache, metrics: Metrics
) -> AsyncIOScheduler:
    grace = {"misfire_grace_time": SCHEDULER_MISFIRE_GRACE}
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        _cache_warmup_job,
        args=(mem, db),
        trigger="cron", hour="*", minute=0,
        id="cache_warmup", replace_existing=True, **grace,
    )
    scheduler.add_job(
        _notifications_job,
        args=(bot, db, mem, metrics),
        trigger="cron", hour="*", minute=5,
        id="notifications", replace_existing=True, **grace,
    )
    scheduler.add_job(
        _weekly_digest_job,
        args=(bot, db, mem, metrics),
        trigger="cron", day_of_week="mon", hour=10, minute=0,
        id="weekly_digest", replace_existing=True, **grace,
    )
    scheduler.add_job(
        _db_cleanup_job,
        args=(db,),
        trigger="cron", day_of_week="sun", hour=4, minute=0,
        id="db_cleanup", replace_existing=True, **grace,
    )

    return scheduler


# ── Session index ─────────────────────────────────────────────────────────────

def _build_session_index(
    sessions: list[Row],
) -> tuple[dict[str, list[Row]], dict[str, list[Row]]]:
    """
    Build two indexes once for O(1) per-user lookup:
      series_idx:  series_id  → [session, ...]
      class_idx:   class_id   → [session, ...]
    """
    series_idx: dict[str, list[Row]] = {}
    class_idx:  dict[str, list[Row]] = {}

    for s in sessions:
        for sr in s.get("series", []):
            series_idx.setdefault(sr["id"], []).append(s)
            for vc in sr.get("vehicleClasses", []):
                class_idx.setdefault(vc["id"], []).append(s)

    return series_idx, class_idx


def _sessions_for_user(
    series_ids: set[str],
    class_ids:  set[str],
    series_idx: dict[str, list[Row]],
    class_idx:  dict[str, list[Row]],
) -> list[Row]:
    seen: set[str] = set()
    result: list[Row] = []
    for sid in series_ids:
        for s in series_idx.get(sid, []):
            if s["id"] not in seen:
                seen.add(s["id"])
                result.append(s)
    for cid in class_ids:
        for s in class_idx.get(cid, []):
            if s["id"] not in seen:
                seen.add(s["id"])
                result.append(s)
    return result


# ── Send helper ───────────────────────────────────────────────────────────────

async def _safe_send(
    bot:     Bot,
    chat_id: int,
    text:    str,
    kb:      InlineKeyboardMarkup,
    db:      Database,
    metrics: Metrics,
) -> bool:
    """
    Send one notification. Returns True on success.
    Handles TelegramForbiddenError (deactivates user) and
    TelegramRetryAfter (waits and retries once).
    """
    async def _do_send() -> None:
        await bot.send_message(
            chat_id, text,
            parse_mode="HTML", reply_markup=kb,
            disable_web_page_preview=True,
        )

    try:
        await _do_send()
        await asyncio.sleep(TELEGRAM_SEND_DELAY)
        return True

    except TelegramForbiddenError:
        await db.deactivate_user(chat_id)
        metrics.blocked_users.inc()
        metrics.record_error("scheduler", f"User {chat_id} blocked bot")
        return False

    except TelegramRetryAfter as exc:
        log.warning("Telegram rate limit: retry after %ds", exc.retry_after)
        await asyncio.sleep(exc.retry_after + 1)
        try:
            await _do_send()
            await asyncio.sleep(TELEGRAM_SEND_DELAY)
            return True
        except Exception as e2:
            log.error("Retry also failed for %d: %s", chat_id, e2)
            metrics.notifications_failed.inc()
            metrics.record_error("scheduler_retry", str(e2))
            return False

    except Exception as exc:
        log.error("Failed to send to %d: %s", chat_id, exc)
        metrics.notifications_failed.inc()
        metrics.record_error("scheduler", str(exc))
        return False


# ── Cache warm-up ─────────────────────────────────────────────────────────────

async def _cache_warmup_job(mem: MemoryCache, db: Database) -> None:
    try:
        await utils.warm_up(mem, db)
        log.info("Cache warm-up done")
    except Exception as exc:
        log.error("Cache warm-up failed: %s", exc)


# ── Session type filtering ─────────────────────────────────────────────────────

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


# ── Notifications job ─────────────────────────────────────────────────────────

async def _notifications_job(
    bot: Bot, db: Database, mem: MemoryCache, metrics: Metrics
) -> None:
    t_start = time.time()
    now     = int(t_start)
    n_start = now - NOTIFICATION_WINDOW
    n_end   = now + max(NOTIFICATION_OFFSETS.values()) + NOTIFICATION_WINDOW

    # ── One API call for everyone ─────────────────────────────────────────────
    try:
        all_sessions   = await utils.get_sessions(mem, db, n_start, n_end)
        all_broadcasts = await utils.get_broadcasts(mem, db, n_start)
        metrics.api_requests.inc(2)
    except Exception as exc:
        log.error("Notification job: API fetch failed: %s", exc)
        metrics.api_errors.inc()
        metrics.record_error("notifications_job", str(exc))
        return

    bc_map = utils.broadcasts_by_session(all_broadcasts)

    # ── One DB round-trip for everyone ────────────────────────────────────────
    all_users  = await db.get_all_users(active_only=True)
    all_subs   = await db.get_all_subscriptions()
    sent_set   = await db.get_all_sent_notifications()

    series_idx, class_idx = _build_session_index(all_sessions)

    # ── Accumulate new notifications to batch-write ───────────────────────────
    to_send:   list[tuple[int, Row, str, list, list[str]]] = []
    to_mark:   list[tuple[int, str, str]] = []

    for user in all_users:
        chat_id    = user["chat_id"]
        subs       = all_subs.get(chat_id, [])
        if not subs:
            continue

        series_ids = {s["ref_id"] for s in subs if s["type"] == "series"}
        class_ids  = {s["ref_id"] for s in subs if s["type"] == "vehicle_class"}
        user_langs = json.loads(user.get("preferred_langs", '["English"]'))

        sessions = _sessions_for_user(series_ids, class_ids, series_idx, class_idx)

        for session in sessions:
            sid      = session.get("id", "")
            start_ts = session.get("start", 0)
            if not start_ts:
                continue

            for notif_type, offset in NOTIFICATION_OFFSETS.items():
                notify_field = f"notify_{notif_type}"
                if not user.get(notify_field, 1 if notif_type in ("1day", "1hour") else 0):
                    continue

                key = (chat_id, sid, notif_type)
                if key in sent_set:
                    continue

                target_ts = start_ts - offset
                if abs(now - target_ts) > NOTIFICATION_WINDOW:
                    continue

                if not _allows_session_type(session, subs):
                    continue

                to_send.append((chat_id, session, notif_type, bc_map.get(sid, []), user_langs))
                to_mark.append(key)
                sent_set.add(key)  # prevent duplicates within same run

    log.info("Notifications to send: %d", len(to_send))

    # ── Send with rate limiting ───────────────────────────────────────────────
    sent_count = 0
    for chat_id, session, notif_type, broadcasts, user_langs in to_send:
        user = next((u for u in all_users if u["chat_id"] == chat_id), None)
        if not user:
            continue

        text = utils.notification_text(
            session,
            notif_type=notif_type,
            broadcasts=broadcasts,
            user_tz=user["timezone"],
            user_langs=user_langs,
        )
        sid = session.get("id", "")
        kb  = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📋 Подробнее", callback_data=f"session:{sid}"),
        ]])

        ok = await _safe_send(bot, chat_id, text, kb, db, metrics)
        if ok:
            sent_count += 1
            metrics.notifications_sent.inc()
            log.info(
                "Sent %s → %d (%s)", notif_type, chat_id, sid[:8]
            )

    # ── Batch-write sent notifications ────────────────────────────────────────
    if to_mark:
        await db.mark_notified_batch(to_mark)

    elapsed = time.time() - t_start
    log.info(
        "Notification job done in %.2fs — sent %d/%d",
        elapsed, sent_count, len(to_send),
    )


# ── Weekly digest job ─────────────────────────────────────────────────────────

async def _weekly_digest_job(
    bot: Bot, db: Database, mem: MemoryCache, metrics: Metrics
) -> None:
    t_start        = time.time()
    w_start, w_end = week_window()
    label          = utils.week_label(w_start)

    try:
        all_sessions   = await utils.get_sessions(mem, db, w_start, w_end)
        all_broadcasts = await utils.get_broadcasts(mem, db, w_start)
        metrics.api_requests.inc(2)
    except Exception as exc:
        log.error("Weekly digest: API fetch failed: %s", exc)
        metrics.api_errors.inc()
        metrics.record_error("weekly_digest", str(exc))
        return

    bc_map     = utils.broadcasts_by_session(all_broadcasts)
    all_users  = await db.get_all_users(active_only=True)
    all_subs   = await db.get_all_subscriptions()
    sent_set   = await db.get_all_sent_notifications()

    series_idx, class_idx = _build_session_index(all_sessions)

    successfully_marked: list[tuple[int, str, str]] = []

    for user in all_users:
        chat_id = user["chat_id"]
        if not user.get("digest_enabled", 0):
            continue

        subs = all_subs.get(chat_id, [])
        if not subs:
            continue

        series_ids = {s["ref_id"] for s in subs if s["type"] == "series"}
        class_ids  = {s["ref_id"] for s in subs if s["type"] == "vehicle_class"}
        user_langs = json.loads(user.get("preferred_langs", '["English"]'))

        sessions = _sessions_for_user(series_ids, class_ids, series_idx, class_idx)

        new_sessions = [
            s for s in sessions
            if ("digest", s["id"]) not in {(k[2], k[1]) for k in sent_set if k[0] == chat_id}
        ]

        try:
            messages = utils.build_digest(
                new_sessions, bc_map, {},
                user_tz=user["timezone"],
                user_langs=user_langs,
                show_no_bc=bool(user.get("show_no_broadcast", 1)),
                header=f"📆 <b>Гонки на неделю</b> — {label}",
            )

            from utils.kb import week_pager, back_to_menu
            reply_markup = (
                week_pager(0, len(messages))
                if len(messages) > 1
                else back_to_menu()
            )
            await bot.send_message(
                chat_id, messages[0],
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=reply_markup,
            )
            await asyncio.sleep(TELEGRAM_SEND_DELAY)

            for s in new_sessions:
                successfully_marked.append((chat_id, s["id"], "digest"))
            metrics.digests_sent.inc()

        except TelegramForbiddenError:
            await db.deactivate_user(chat_id)
            metrics.blocked_users.inc()

        except TelegramRetryAfter as exc:
            log.warning("Rate limit during digest: sleeping %ds", exc.retry_after)
            await asyncio.sleep(exc.retry_after + 1)

        except Exception as exc:
            log.error("Digest failed for %d: %s", chat_id, exc)
            metrics.record_error("weekly_digest", str(exc))

    if successfully_marked:
        await db.mark_notified_batch(successfully_marked)

    log.info("Weekly digest done — sent to %d users", len(successfully_marked))


# ── DB cleanup job ────────────────────────────────────────────────────────────

async def _db_cleanup_job(db: Database) -> None:
    deleted = await db.cleanup_old_notifications()
    log.info("DB cleanup: %d old sent_notifications removed", deleted)
