"""
Scheduler jobs:
  cache_warmup    — каждый час :00  — прогрев L1+L2
  notifications   — каждый час :05  — уведомления о гонках
  weekly_digest   — каждые 5 мин — еженедельный дайджест по локальному времени пользователя
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
from datetime import datetime, time as dt_time, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import pytz

from config import ADMIN_IDS
from database import Database
from utils.backups import send_db_backup
from utils.cache import MemoryCache
from utils.health import RuntimeState
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
_DIGEST_WINDOW_SECONDS = 5 * 60
_RETRY_BASE_DELAY_SECONDS = 60
_RETRY_MAX_ATTEMPTS = 4


def _mark_scheduler_job_run(state: RuntimeState, job_name: str) -> None:
    jobs = getattr(state, "scheduler_jobs", None)
    if jobs is None:
        jobs = {}
        setattr(state, "scheduler_jobs", jobs)
    jobs[job_name] = datetime.now(timezone.utc).isoformat()


def make_scheduler(
    bot: Bot, db: Database, mem: MemoryCache, metrics: Metrics, state: RuntimeState
) -> AsyncIOScheduler:
    grace = {"misfire_grace_time": SCHEDULER_MISFIRE_GRACE}
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        _cache_warmup_job,
        args=(mem, db, state),
        trigger="cron", hour="*", minute=0,
        id="cache_warmup", replace_existing=True, **grace,
    )
    scheduler.add_job(
        _notifications_job,
        args=(bot, db, mem, metrics, state),
        trigger="cron", hour="*", minute=5,
        id="notifications", replace_existing=True, **grace,
    )
    scheduler.add_job(
        _weekly_digest_job,
        args=(bot, db, mem, metrics, state),
        trigger="cron", minute="*/5",
        id="weekly_digest", replace_existing=True, **grace,
    )
    scheduler.add_job(
        _db_cleanup_job,
        args=(db, state),
        trigger="cron", day_of_week="sun", hour=4, minute=0,
        id="db_cleanup", replace_existing=True, **grace,
    )
    scheduler.add_job(
        _retry_delivery_job,
        args=(bot, db, metrics, state),
        trigger="cron", minute="*",
        id="retry_delivery", replace_existing=True, **grace,
    )
    scheduler.add_job(
        _session_reminders_job,
        args=(bot, db, mem, metrics, state),
        trigger="cron", minute="*",
        id="session_reminders", replace_existing=True, **grace,
    )
    scheduler.add_job(
        _rscg_notifications_job,
        args=(bot, db, mem, metrics, state),
        trigger="cron", hour="*", minute=10,
        id="rscg_notifications", replace_existing=True, **grace,
    )
    scheduler.add_job(
        _admin_backup_job,
        args=(bot, db, state),
        trigger="cron", hour=1, minute=30,
        id="admin_backup", replace_existing=True, **grace,
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

def _retry_delay(attempt: int) -> int:
    return _RETRY_BASE_DELAY_SECONDS * (2 ** max(0, attempt - 1))


async def _record_delivery_success(
    db: Database,
    metrics: Metrics,
    item: utils.PendingDelivery,
) -> None:
    await asyncio.sleep(TELEGRAM_SEND_DELAY)
    if item.kind == "notification" and item.session_id and item.notif_type:
        await db.mark_notified_batch([(item.chat_id, item.session_id, item.notif_type)])
        metrics.notifications_sent.inc()
    elif item.kind == "digest" and item.digest_session_ids:
        await db.mark_notified_batch(
            [(item.chat_id, session_id, "digest") for session_id in item.digest_session_ids]
        )
        metrics.digests_sent.inc()
    elif item.kind == "session_reminder" and item.session_id and item.remind_type:
        await db.remove_session_reminder(item.chat_id, item.session_id, item.remind_type)
        metrics.notifications_sent.inc()
    log.info("Delivered %s → %d", item.kind, item.chat_id)


async def _process_delivery(
    bot: Bot,
    db: Database,
    metrics: Metrics,
    item: utils.PendingDelivery,
    *,
    allow_queue: bool,
) -> bool:
    result = await utils.send_delivery(bot, item)

    if result.status == "success":
        await _record_delivery_success(db, metrics, item)
        return True

    if result.status == "blocked":
        await db.deactivate_user(item.chat_id)
        metrics.blocked_users.inc()
        metrics.record_error(item.kind, f"User {item.chat_id} blocked bot")
        log.info("Delivery blocked by user %d for %s", item.chat_id, item.kind)
        return False

    item.attempts += 1
    item.last_error = result.error
    if item.attempts <= _RETRY_MAX_ATTEMPTS and allow_queue:
        delay = result.retry_delay or _retry_delay(item.attempts)
        queued = await db.enqueue_pending_delivery(item, delay_seconds=delay)
        if queued:
            log.warning(
                "Queued %s → %d for retry in %.0fs (attempt %d/%d): %s",
                item.kind, item.chat_id, delay, item.attempts, _RETRY_MAX_ATTEMPTS, result.error,
            )
        return False

    if item.attempts > _RETRY_MAX_ATTEMPTS:
        metrics.notifications_failed.inc()
        metrics.record_error(item.kind, result.error or "delivery failed")
        log.error(
            "Delivery failed permanently for %s → %d after %d attempts: %s",
            item.kind, item.chat_id, item.attempts, result.error,
        )
    return False


# ── Cache warm-up ─────────────────────────────────────────────────────────────

async def _cache_warmup_job(mem: MemoryCache, db: Database, state: RuntimeState) -> None:
    started_at = time.time()
    try:
        ok = await utils.warm_up(mem, db, state.http_session)
        if ok:
            state.mark_job_success("cache_warmup", int((time.time() - started_at) * 1000))
            _mark_scheduler_job_run(state, "cache_warmup")
            log.info("Cache warm-up done")
        elif ok is None:
            log.warning("Cache warm-up skipped: upstream API unavailable")
        else:
            state.mark_job_failure(
                "cache_warmup", "warm-up failed", int((time.time() - started_at) * 1000)
            )
    except Exception as exc:
        state.mark_job_failure("cache_warmup", str(exc), int((time.time() - started_at) * 1000))
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


def _in_quiet_hours(now_ts: int, user: Row) -> bool:
    if not user.get("quiet_enabled", 0):
        return False

    start = int(user.get("quiet_start", 23))
    end = int(user.get("quiet_end", 7))
    local_hour = datetime.fromtimestamp(
        now_ts, tz=timezone.utc
    ).astimezone(pytz.timezone(user["timezone"])).hour

    if start == end:
        return True
    if start < end:
        return start <= local_hour < end
    return local_hour >= start or local_hour < end


def _digest_due_now(now_ts: int, user: Row) -> bool:
    tz = pytz.timezone(user["timezone"])
    local_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc).astimezone(tz)
    if local_dt.weekday() != 0:
        return False

    try:
        hh_raw, mm_raw = str(user.get("digest_time", "08:00")).split(":", 1)
        digest_hour = int(hh_raw)
        digest_minute = int(mm_raw)
    except Exception:
        digest_hour, digest_minute = 8, 0

    scheduled = local_dt.replace(
        hour=digest_hour,
        minute=digest_minute,
        second=0,
        microsecond=0,
    )
    delta = abs((local_dt - scheduled).total_seconds())
    return delta < _DIGEST_WINDOW_SECONDS


async def _retry_delivery_job(bot: Bot, db: Database, metrics: Metrics, state: RuntimeState) -> None:
    started_at = time.time()
    due = await db.get_due_pending_deliveries(started_at)
    if not due:
        state.mark_job_success("retry_delivery", int((time.time() - started_at) * 1000))
        return

    log.info("Retry queue: processing %d pending deliveries", len(due))
    for item in due:
        result = await utils.send_delivery(bot, item)
        if result.status == "success":
            await _record_delivery_success(db, metrics, item)
            if item.kind == "broadcast":
                log.info("Broadcast delivery retried successfully for %d", item.chat_id)
            await db.complete_pending_delivery(item)
            continue
        if result.status == "blocked":
            await db.deactivate_user(item.chat_id)
            metrics.blocked_users.inc()
            metrics.record_error(item.kind, f"User {item.chat_id} blocked bot")
            await db.complete_pending_delivery(item)
            continue

        item.attempts += 1
        item.last_error = result.error
        if item.attempts > _RETRY_MAX_ATTEMPTS:
            metrics.notifications_failed.inc()
            metrics.record_error(item.kind, result.error or "delivery failed")
            log.error(
                "Delivery failed permanently for %s → %d after %d attempts: %s",
                item.kind, item.chat_id, item.attempts, result.error,
            )
            await db.complete_pending_delivery(item)
            continue

        delay = result.retry_delay or _retry_delay(item.attempts)
        await db.requeue_pending_delivery(item, delay_seconds=delay)
        log.warning(
            "Requeued %s → %d for retry in %.0fs (attempt %d/%d): %s",
            item.kind, item.chat_id, delay, item.attempts, _RETRY_MAX_ATTEMPTS, item.last_error,
        )
    state.mark_job_success("retry_delivery", int((time.time() - started_at) * 1000))


async def _session_reminders_job(
    bot: Bot, db: Database, mem: MemoryCache, metrics: Metrics, state: RuntimeState
) -> None:
    started_at = time.time()
    now_ts = int(started_at)
    rows = await db.get_due_session_reminders(now_ts)
    if not rows:
        state.mark_job_success("session_reminders", int((time.time() - started_at) * 1000))
        return

    sent_count = 0
    users_by_chat_id: dict[int, Row | None] = {}
    session_context_by_id: dict[str, tuple[Row | None, list[Row], list[Row]]] = {}
    for row in rows:
        chat_id = row["chat_id"]
        session_id = row["session_id"]

        if chat_id not in users_by_chat_id:
            users_by_chat_id[chat_id] = await db.get_user(chat_id)
        user = users_by_chat_id[chat_id]
        if not user:
            continue

        if session_id not in session_context_by_id:
            session_context_by_id[session_id] = await utils.load_session_context(
                db, mem, state.http_session, session_id
            )
        session, broadcasts, live_timings = session_context_by_id[session_id]
        if not session:
            await db.remove_session_reminder(chat_id, session_id, row["remind_type"])
            continue

        user_langs = json.loads(user.get("preferred_langs", '["English"]'))
        ui_lang = utils.get_ui_lang(user)
        labels = {
            "1day": "🔔 Session reminder: starts in 1 day" if ui_lang == "en" else "🔔 Напоминание по сессии: старт через сутки",
            "1hour": "🚨 Session reminder: starts in 1 hour" if ui_lang == "en" else "🚨 Напоминание по сессии: старт через час",
            "start": "🏁 Session reminder: starts now" if ui_lang == "en" else "🏁 Напоминание по сессии: старт сейчас",
        }
        text = (
            f"{labels.get(row['remind_type'], '🔔 Session reminder' if ui_lang == 'en' else '🔔 Напоминание по сессии')}\n\n"
            f"{utils.session_card(session, broadcasts, live_timings, user['timezone'], user_langs, ui_lang=ui_lang) or session.get('name', 'Session' if ui_lang == 'en' else 'Сессия')}"
        )
        event_identity = utils.build_event_identity(session, ui_lang)
        dedupe_key = ("session_reminder", chat_id, session_id, row["remind_type"])
        if await db.has_pending_delivery(dedupe_key):
            continue
        item = utils.PendingDelivery(
            kind="session_reminder",
            chat_id=chat_id,
            text=text,
            reply_markup=utils.notification_actions(session_id, event_identity.key, False, False, ui_lang),
            dedupe_key=dedupe_key,
            session_id=session_id,
            remind_type=row["remind_type"],
        )
        ok = await _process_delivery(bot, db, metrics, item, allow_queue=True)
        if ok:
            sent_count += 1

    elapsed = time.time() - started_at
    state.mark_job_success("session_reminders", int(elapsed * 1000))
    log.info("Session reminders job done in %.2fs — sent %d/%d", elapsed, sent_count, len(rows))


# ── Notifications job ─────────────────────────────────────────────────────────

async def _notifications_job(
    bot: Bot, db: Database, mem: MemoryCache, metrics: Metrics, state: RuntimeState
) -> None:
    t_start = time.time()
    now     = int(t_start)
    n_start = now - NOTIFICATION_WINDOW
    n_end   = now + max(NOTIFICATION_OFFSETS.values()) + NOTIFICATION_WINDOW

    # ── One API call for everyone ─────────────────────────────────────────────
    try:
        all_sessions   = await utils.get_sessions(mem, db, state.http_session, n_start, n_end)
        all_broadcasts = await utils.get_broadcasts(mem, db, state.http_session, n_start)
        metrics.api_requests.inc(2)
    except Exception as exc:
        if utils.is_expected_api_failure(exc):
            log.warning("Notification job skipped: upstream API unavailable: %s", exc)
            metrics.api_errors.inc()
            return
        state.mark_job_failure("notifications", str(exc), int((time.time() - t_start) * 1000))
        log.error("Notification job: API fetch failed: %s", exc)
        metrics.api_errors.inc()
        metrics.record_error("notifications_job", str(exc))
        return

    bc_map = utils.broadcasts_by_session(all_broadcasts)
    session_event_map = utils.map_sessions_to_events(all_sessions)

    # ── One DB round-trip for everyone ────────────────────────────────────────
    all_users  = await db.get_all_users(active_only=True)
    all_subs   = await db.get_all_subscriptions()
    sent_set   = await db.get_all_sent_notifications()
    users_by_chat_id = {user["chat_id"]: user for user in all_users}

    series_idx, class_idx = _build_session_index(all_sessions)

    # ── Accumulate new notifications to batch-write ───────────────────────────
    to_send: list[tuple[Row, Row, str, list, list[dict], list[str], str, dict]] = []

    live_timings_cache: dict[str, list[dict]] = {}
    for user in all_users:
        chat_id    = user["chat_id"]
        subs       = all_subs.get(chat_id, [])
        if not subs:
            continue
        ignored_keys = {
            row["event_key"]
            for row in await db.get_ignored_events(chat_id, now)
        }

        series_ids = {s["ref_id"] for s in subs if s["type"] == "series"}
        class_ids  = {s["ref_id"] for s in subs if s["type"] == "vehicle_class"}
        user_langs = json.loads(user.get("preferred_langs", '["English"]'))
        ui_lang = utils.get_ui_lang(user)
        if _in_quiet_hours(now, user):
            continue

        sessions = _sessions_for_user(series_ids, class_ids, series_idx, class_idx)

        for session in sessions:
            sid      = session.get("id", "")
            start_ts = session.get("start", 0)
            if not start_ts:
                continue
            event = session_event_map.get(sid)
            event_key = event["event_key"] if event else utils.build_event_identity(session, ui_lang).key
            if event_key in ignored_keys:
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

                if not user.get("show_no_broadcast", 1) and not bc_map.get(sid):
                    continue

                if sid not in live_timings_cache:
                    try:
                        live_timings_cache[sid] = await utils.get_live_timings(sid, state.http_session)
                    except Exception as exc:
                        log.warning("Live timings fetch failed for %s: %s", sid, exc)
                    live_timings_cache[sid] = []

                to_send.append((
                    user,
                    session,
                    notif_type,
                    bc_map.get(sid, []),
                    live_timings_cache[sid],
                    user_langs,
                    ui_lang,
                    event or {
                        "event_key": event_key,
                        "title": utils.build_event_identity(session, ui_lang).title,
                        "sort_ts": int(session.get("start", 0) or 0),
                    },
                ))
                sent_set.add(key)  # prevent duplicates within same run

    log.info("Notifications to send: %d", len(to_send))

    # ── Send with retries / queue fallback ────────────────────────────────────
    sent_count = 0
    for queued_user, session, notif_type, broadcasts, live_timings, user_langs, ui_lang, event in to_send:
        chat_id = queued_user["chat_id"]
        user = users_by_chat_id.get(chat_id)
        if not user:
            continue

        text = utils.notification_text(
            session,
            broadcasts=broadcasts,
            live_timings=live_timings,
            user_tz=user["timezone"],
            user_langs=user_langs,
            notif_type=notif_type,
            ui_lang=ui_lang,
        )
        sid = session.get("id", "")
        kb = utils.notification_actions(sid, event["event_key"], False, False, ui_lang)
        dedupe_key = ("notification", chat_id, sid, notif_type)
        if await db.has_pending_delivery(dedupe_key):
            continue
        item = utils.PendingDelivery(
            kind="notification",
            chat_id=chat_id,
            text=text,
            reply_markup=kb,
            dedupe_key=dedupe_key,
            session_id=sid,
            notif_type=notif_type,
        )
        ok = await _process_delivery(bot, db, metrics, item, allow_queue=True)
        if ok:
            sent_count += 1
            log.info(
                "Sent %s → %d (%s)", notif_type, chat_id, sid[:8]
            )

    elapsed = time.time() - t_start
    state.mark_job_success("notifications", int(elapsed * 1000))
    _mark_scheduler_job_run(state, "notifications")
    log.info(
        "Notification job done in %.2fs — sent %d/%d",
        elapsed, sent_count, len(to_send),
    )


def _rscg_start_ts(stage: utils.RscgStage) -> int:
    moscow_tz = timezone(timedelta(hours=3))
    start_dt = datetime.combine(stage.date_start, dt_time(hour=10, minute=0), tzinfo=moscow_tz)
    return int(start_dt.timestamp())


async def _rscg_notifications_job(
    bot: Bot, db: Database, mem: MemoryCache, metrics: Metrics, state: RuntimeState
) -> None:
    started_at = time.time()
    now_ts = int(started_at)
    allowed_notif_types = ("3days", "1day", "start")

    try:
        stages = await utils.get_rscg_stages(mem, db, state.http_session)
    except Exception as exc:
        state.mark_job_failure("rscg_notifications", str(exc), int((time.time() - started_at) * 1000))
        log.error("RSCG notifications: fetch failed: %s", exc)
        metrics.record_error("rscg_notifications", str(exc))
        return

    if not stages:
        state.mark_job_success("rscg_notifications", int((time.time() - started_at) * 1000))
        _mark_scheduler_job_run(state, "rscg_notifications")
        return

    all_users = await db.get_all_users(active_only=True)
    all_subs = await db.get_all_subscriptions()
    sent_set = await db.get_all_sent_notifications()
    to_send: list[tuple[Row, utils.RscgStage, str]] = []

    for user in all_users:
        chat_id = user["chat_id"]
        subs = all_subs.get(chat_id, [])
        if not any(sub["type"] == "rscg" and sub["ref_id"] == "rscg" for sub in subs):
            continue
        if _in_quiet_hours(now_ts, user):
            continue

        for stage in stages:
            session_id = f"rscg_{stage.id}"
            stage_start_ts = _rscg_start_ts(stage)
            for notif_type in allowed_notif_types:
                if not user.get(f"notify_{notif_type}", 1 if notif_type == "1day" else 0):
                    continue
                key = (chat_id, session_id, notif_type)
                if key in sent_set:
                    continue
                target_ts = stage_start_ts - NOTIFICATION_OFFSETS[notif_type]
                if abs(now_ts - target_ts) > NOTIFICATION_WINDOW:
                    continue
                to_send.append((user, stage, notif_type))
                sent_set.add(key)

    sent_count = 0
    for user, stage, notif_type in to_send:
        chat_id = user["chat_id"]
        session_id = f"rscg_{stage.id}"
        ui_lang = utils.get_ui_lang(user)
        text = utils.rscg_notification_text(stage, notif_type, ui_lang=ui_lang)
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="📋 Details" if ui_lang == "en" else "📋 Подробнее",
                callback_data=utils.RscgCD(action="stage", stage_id=stage.id).pack(),
            ),
        ]])
        dedupe_key = ("notification", chat_id, session_id, notif_type)
        if await db.has_pending_delivery(dedupe_key):
            continue
        item = utils.PendingDelivery(
            kind="notification",
            chat_id=chat_id,
            text=text,
            reply_markup=kb,
            dedupe_key=dedupe_key,
            session_id=session_id,
            notif_type=notif_type,
        )
        ok = await _process_delivery(bot, db, metrics, item, allow_queue=True)
        if ok:
            sent_count += 1

    elapsed = time.time() - started_at
    state.mark_job_success("rscg_notifications", int(elapsed * 1000))
    _mark_scheduler_job_run(state, "rscg_notifications")
    log.info("RSCG notifications done in %.2fs — sent %d/%d", elapsed, sent_count, len(to_send))


# ── Weekly digest job ─────────────────────────────────────────────────────────

async def _weekly_digest_job(
    bot: Bot, db: Database, mem: MemoryCache, metrics: Metrics, state: RuntimeState
) -> None:
    t_start        = time.time()
    now_ts         = int(t_start)
    w_start, w_end = week_window()
    label          = utils.week_label(w_start, w_end)

    try:
        all_sessions   = await utils.get_sessions(mem, db, state.http_session, w_start, w_end)
        all_broadcasts = await utils.get_broadcasts(mem, db, state.http_session, w_start)
        metrics.api_requests.inc(2)
    except Exception as exc:
        if utils.is_expected_api_failure(exc):
            log.warning("Weekly digest skipped: upstream API unavailable: %s", exc)
            metrics.api_errors.inc()
            return
        state.mark_job_failure("weekly_digest", str(exc), int((time.time() - t_start) * 1000))
        log.error("Weekly digest: API fetch failed: %s", exc)
        metrics.api_errors.inc()
        metrics.record_error("weekly_digest", str(exc))
        return

    bc_map     = utils.broadcasts_by_session(all_broadcasts)
    all_users  = await db.get_all_users(active_only=True)
    all_subs   = await db.get_all_subscriptions()
    sent_set   = await db.get_all_sent_notifications()
    sent_digest_by_chat: dict[int, set[str]] = {}
    for sent_chat_id, session_id, notif_type in sent_set:
        if notif_type != "digest":
            continue
        sent_digest_by_chat.setdefault(sent_chat_id, set()).add(session_id)

    series_idx, class_idx = _build_session_index(all_sessions)

    sent_count = 0

    for user in all_users:
        chat_id = user["chat_id"]
        if not user.get("digest_enabled", 0):
            continue
        if not _digest_due_now(now_ts, user):
            continue

        subs = all_subs.get(chat_id, [])
        if not subs:
            continue

        series_ids = {s["ref_id"] for s in subs if s["type"] == "series"}
        class_ids  = {s["ref_id"] for s in subs if s["type"] == "vehicle_class"}
        user_langs = json.loads(user.get("preferred_langs", '["English"]'))
        ui_lang = utils.get_ui_lang(user)

        sessions = _sessions_for_user(series_ids, class_ids, series_idx, class_idx)
        sessions = [session for session in sessions if _allows_session_type(session, subs)]
        sent_digest_ids = sent_digest_by_chat.get(chat_id, set())

        new_sessions = [
            s for s in sessions
            if s["id"] not in sent_digest_ids
        ]
        header = f"{'📆 <b>Races This Week</b>' if ui_lang == 'en' else '📆 <b>Гонки на неделю</b>'} — {label}"
        if len(subs) > 1:
            series_count = sum(1 for sub in subs if sub["type"] == "series")
            class_count = sum(1 for sub in subs if sub["type"] == "vehicle_class")
            messages = [utils.tr(
                ui_lang,
                "digest.summary",
                header=header,
                count=len(new_sessions),
                period=utils.tr(ui_lang, "digest.period_week"),
                series_count=series_count,
                class_count=class_count,
            )]
            reply_markup = utils.digest_pick_menu("week", subs, 0, lang=ui_lang)
        else:
            messages = utils.build_digest(
                new_sessions, bc_map, {},
                user_tz=user["timezone"],
                user_langs=user_langs,
                show_no_bc=bool(user.get("show_no_broadcast", 1)),
                header=header,
                ui_lang=ui_lang,
            )
            reply_markup = utils.digest_view_menu(
                "week",
                0,
                len(messages),
                selected_sub=subs[0] if subs else None,
                allow_pick=False,
                lang=ui_lang,
            )
        dedupe_key = ("digest", chat_id, tuple(sorted(s["id"] for s in new_sessions)))
        if await db.has_pending_delivery(dedupe_key):
            continue
        item = utils.PendingDelivery(
            kind="digest",
            chat_id=chat_id,
            text=messages[0],
            reply_markup=reply_markup,
            dedupe_key=dedupe_key,
            digest_session_ids=tuple(s["id"] for s in new_sessions),
        )
        ok = await _process_delivery(bot, db, metrics, item, allow_queue=True)
        if ok:
            sent_count += 1

    elapsed = time.time() - t_start
    state.mark_job_success("weekly_digest", int(elapsed * 1000))
    _mark_scheduler_job_run(state, "weekly_digest")
    log.info("Weekly digest done in %.2fs — sent to %d users", elapsed, sent_count)


# ── DB cleanup job ────────────────────────────────────────────────────────────

async def _db_cleanup_job(db: Database, state: RuntimeState) -> None:
    started_at = time.time()
    deleted = await db.cleanup_old_notifications()
    deleted += await db.cleanup_expired_ignored_events(int(started_at))
    state.mark_job_success("db_cleanup", int((time.time() - started_at) * 1000))
    log.info("DB cleanup: %d old sent_notifications removed", deleted)


async def _admin_backup_job(bot: Bot, db: Database, state: RuntimeState) -> None:
    started_at = time.time()
    if not ADMIN_IDS:
        state.mark_job_success("admin_backup", int((time.time() - started_at) * 1000))
        return

    try:
        await send_db_backup(
            bot,
            ADMIN_IDS,
            db,
            caption_prefix="Daily DB backup ZIP",
        )
        state.mark_job_success("admin_backup", int((time.time() - started_at) * 1000))
    except Exception as exc:
        state.mark_job_failure("admin_backup", str(exc), int((time.time() - started_at) * 1000))
        log.error("Admin backup failed: %s", exc)
