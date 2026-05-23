"""
Admin panel — accessible only to ADMIN_IDS.

Commands:
  /admin          — main dashboard
  /admin_users    — user stats
  /admin_logs     — recent event log
  /admin_cache    — cache status + clear
  /admin_errors   — recent errors from metrics
  /admin_broadcast <text> — send message to all active users
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import ADMIN_IDS, TELEGRAM_SEND_DELAY
from database import Database
import utils
from utils.cache import MemoryCache
from utils.metrics import Metrics

log = logging.getLogger(__name__)
router = Router()


# ── Guard filter ──────────────────────────────────────────────────────────────

def _is_admin(message: Message) -> bool:
    return message.from_user.id in ADMIN_IDS


def _user_kb(chat_id: int, is_active: bool = True) -> InlineKeyboardMarkup:
    action_btn = (
        InlineKeyboardButton(text="⛔ Деактивировать", callback_data=f"adm:user_deactivate:{chat_id}")
        if is_active else
        InlineKeyboardButton(text="✅ Активировать", callback_data=f"adm:user_activate:{chat_id}")
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧪 Тест", callback_data=f"adm:user_ping:{chat_id}"),
            InlineKeyboardButton(text="🐞 Debug", callback_data=f"adm:user_debug:{chat_id}"),
        ],
        [action_btn],
        [InlineKeyboardButton(text="◀️ К пользователям", callback_data="adm:users")],
    ])


def _parse_admin_send_args(text: str) -> tuple[int, str]:
    parts = text.split(maxsplit=2)
    if len(parts) < 3:
        raise ValueError("usage")
    chat_id = int(parts[1])
    body = parts[2].strip()
    if not body:
        raise ValueError("empty")
    return chat_id, body


async def _render_user_card(chat_id: int, db: Database) -> tuple[str, bool] | tuple[None, None]:
    user = await db.get_user(chat_id)
    if not user:
        return None, None
    counts = await db.get_user_counts(chat_id)
    langs = ", ".join(json.loads(user.get("preferred_langs", '["English"]')))
    username = escape(user.get("username") or "—")
    return (
        f"👤 <b>Пользователь {chat_id}</b>\n\n"
        f"Username: <b>{username}</b>\n"
        f"Активен: <b>{'да' if user['is_active'] else 'нет'}</b>\n"
        f"Таймзона: <code>{user['timezone']}</code>\n"
        f"Языки: <b>{escape(langs)}</b>\n"
        f"Дайджест: {'вкл' if user['digest_enabled'] else 'выкл'} в {user['digest_time']}\n"
        f"Тихие часы: {'вкл' if user['quiet_enabled'] else 'выкл'} ({user['quiet_start']}:00–{user['quiet_end']}:00)\n"
        f"Последняя активность: <code>{user['last_seen_at']}</code>\n"
        f"Создан: <code>{user['created_at']}</code>\n\n"
        f"Подписки: <b>{counts['subscriptions']}</b>\n"
        f"Избранное: <b>{counts['favorites']}</b>\n"
        f"Персональные reminder'ы: <b>{counts['reminders']}</b>\n"
        f"Отправленных уведомлений: <b>{counts['sent_notifications']}</b>"
    ), bool(user["is_active"])


async def _render_user_debug(chat_id: int, db: Database) -> str | None:
    user = await db.get_user(chat_id)
    if not user:
        return None
    subs = await db.get_subscriptions(chat_id)
    sent = await db.get_user_sent_notifications(chat_id, limit=8)
    events = await db.get_user_event_log(chat_id, limit=8)

    subs_text = "\n".join(
        f"  {s['type']} | {escape(s['ref_name'])} | qual={s.get('qualifying_notify', s.get('qual_notify', 1))} | practice={s.get('practice_notify', s.get('qual_notify', 1))}"
        for s in subs[:10]
    ) or "  —"
    sent_text = "\n".join(
        f"  {row['sent_at'][:16]} | {row['notif_type']} | {row['session_id'][:8]}"
        for row in sent
    ) or "  —"
    event_lines = []
    for row in events:
        payload = ""
        if row.get("payload"):
            payload = f" | {escape(str(row['payload'])[:60])}"
        event_lines.append(f"  {row['ts'][:16]} | {row['event_type']}{payload}")
    events_text = "\n".join(event_lines) or "  —"

    return (
        f"🐞 <b>Debug user {chat_id}</b>\n\n"
        f"<b>Raw profile</b>\n"
        f"<pre>{escape(json.dumps(dict(user), ensure_ascii=False, indent=2))}</pre>\n"
        f"<b>Subscriptions</b>\n<pre>{subs_text}</pre>\n"
        f"<b>Recent sent notifications</b>\n<pre>{sent_text}</pre>\n"
        f"<b>Recent events</b>\n<pre>{events_text}</pre>"
    )


def _admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data="adm:users"),
            InlineKeyboardButton(text="📊 Метрики",      callback_data="adm:metrics"),
        ],
        [
            InlineKeyboardButton(text="📋 Лог событий",  callback_data="adm:log"),
            InlineKeyboardButton(text="⚠️ Ошибки",       callback_data="adm:errors"),
        ],
        [
            InlineKeyboardButton(text="🗄 Кэш",          callback_data="adm:cache"),
            InlineKeyboardButton(text="🔄 Прогреть кэш", callback_data="adm:warmup"),
        ],
        [
            InlineKeyboardButton(text="🔃 Обновить",     callback_data="adm:refresh"),
        ],
    ])


# ── Dashboard ─────────────────────────────────────────────────────────────────

async def _dashboard_text(
    db: Database, mem: MemoryCache, metrics: Metrics, state: utils.RuntimeState
) -> str:
    stats = await db.get_stats()
    m     = metrics.summary()
    fallback = utils.fallback_stats()
    now   = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    cache_total = m["cache_l1_hits"] + m["cache_l2_hits"] + m["cache_misses"]
    l1_pct = int(m["cache_l1_hits"] / cache_total * 100) if cache_total else 0
    l2_pct = int(m["cache_l2_hits"] / cache_total * 100) if cache_total else 0

    top_cmd = "\n".join(
        f"  /{cmd}: {n}" for cmd, n in m["top_commands"][:5]
    ) or "  —"
    jobs = state.scheduler_jobs

    def _job_line(name: str, label: str) -> str:
        ts = jobs.get(name)
        if not ts:
            return f"  {label}: <i>ещё не запускался</i>"
        return f"  {label}: <code>{ts[11:16]} UTC</code>"

    scheduler_text = "\n".join([
        _job_line("cache_warmup", "🗄 Кэш"),
        _job_line("notifications", "🔔 Уведомления"),
        _job_line("weekly_digest", "📆 Дайджест"),
        _job_line("rscg_notifications", "🏎️ РСКГ"),
    ])

    return (
        f"🛠 <b>Панель администратора</b>\n"
        f"<code>{now}</code>\n"
        f"⏱ Uptime: <b>{m['uptime']}</b>\n"
        f"\n"
        f"<b>👥 Пользователи</b>\n"
        f"  Всего: {stats['total']} | Активных: {stats['active']}\n"
        f"  Заблокировали бота: {stats['blocked']}\n"
        f"  Новых сегодня: {stats['new_today']} | За неделю: {stats['new_week']}\n"
        f"  Подписок: {stats['subs']}\n"
        f"\n"
        f"<b>📨 Сообщения</b>\n"
        f"  Получено: {m['messages_received']} | За час: {m['messages_per_hour']}\n"
        f"  Топ команды:\n{top_cmd}\n"
        f"\n"
        f"<b>🔔 Уведомления</b>\n"
        f"  Отправлено (сессия): {m['notifications_sent']}\n"
        f"  Ошибок: {m['notifications_failed']}\n"
        f"  Дайджестов: {m['digests_sent']}\n"
        f"  За 24ч (БД): {stats['notifs_last_24h']}\n"
        f"\n"
        f"<b>🗄 Кэш L1 (память)</b>\n"
        f"  Записей: {mem.size()}\n"
        f"  L1 hit: {l1_pct}% | L2 hit: {l2_pct}%\n"
        f"  API запросов: {m['api_requests']} | Ошибок: {m['api_errors']}\n"
        f"  Fallback на stale cache: {fallback['count']}\n"
        f"\n"
        f"<b>⏰ Шедулер (последний запуск)</b>\n"
        f"{scheduler_text}\n"
        f"\n"
        f"<b>📬 Retry queue</b>\n"
        f"  В очереди: {utils.delivery_queue.size()}\n"
    )


@router.message(Command("admin"))
async def cmd_admin(
    message: Message, db: Database, mem: MemoryCache, metrics: Metrics, runtime_state: utils.RuntimeState
) -> None:
    if not _is_admin(message):
        return
    text = await _dashboard_text(db, mem, metrics, runtime_state)
    await message.answer(text, parse_mode="HTML", reply_markup=_admin_kb())


@router.callback_query(F.data == "adm:refresh")
async def cb_refresh(
    callback: CallbackQuery, db: Database, mem: MemoryCache, metrics: Metrics, runtime_state: utils.RuntimeState
) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    text = await _dashboard_text(db, mem, metrics, runtime_state)
    await utils.safe_edit_text(callback.message, text, parse_mode="HTML", reply_markup=_admin_kb())
    await callback.answer("Обновлено")


# ── Users panel ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:users")
async def cb_users(callback: CallbackQuery, db: Database) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return

    stats = await db.get_stats()

    # Top timezones
    tz_rows = await db._fetchall(
        "SELECT timezone, COUNT(*) n FROM users WHERE is_active=1 "
        "GROUP BY timezone ORDER BY n DESC LIMIT 5"
    )
    tz_text = "\n".join(f"  {r['timezone']}: {r['n']}" for r in tz_rows) or "  —"

    # Top langs
    lang_rows = await db._fetchall(
        "SELECT preferred_langs, COUNT(*) n FROM users WHERE is_active=1 "
        "GROUP BY preferred_langs ORDER BY n DESC LIMIT 5"
    )
    lang_text = "\n".join(
        f"  {r['preferred_langs']}: {r['n']}" for r in lang_rows
    ) or "  —"

    # Recent registrations
    recent = await db._fetchall(
        "SELECT chat_id, username, created_at FROM users "
        "ORDER BY created_at DESC LIMIT 5"
    )
    recent_text = "\n".join(
        f"  {r['created_at'][:16]} — @{escape(r['username'] or str(r['chat_id']))}"
        for r in recent
    ) or "  —"
    top_subs = await db._fetchall(
        "SELECT ref_name, type, COUNT(*) n FROM subscriptions "
        "GROUP BY type, ref_id ORDER BY n DESC LIMIT 5"
    )
    top_subs_text = "\n".join(
        f"  {escape(r['ref_name'])} ({escape(r['type'])}): {r['n']}"
        for r in top_subs
    ) or "  —"

    text = (
        f"👥 <b>Пользователи</b>\n\n"
        f"Всего: <b>{stats['total']}</b>\n"
        f"Активных: <b>{stats['active']}</b>\n"
        f"Заблокировали бота: <b>{stats['blocked']}</b>\n"
        f"Новых сегодня: <b>{stats['new_today']}</b>\n"
        f"Новых за неделю: <b>{stats['new_week']}</b>\n\n"
        f"<b>🌍 Топ таймзон:</b>\n{tz_text}\n\n"
        f"<b>🌐 Топ языков:</b>\n{lang_text}\n\n"
        f"<b>🏁 Топ подписок:</b>\n{top_subs_text}\n\n"
        f"<b>🕐 Последние регистрации:</b>\n{recent_text}\n\n"
        f"Для детального просмотра используйте <code>/admin_user CHAT_ID</code> или <code>/admin_user @username</code>."
    )
    rows = [
        [InlineKeyboardButton(text=f"👤 {r['chat_id']}", callback_data=f"adm:user:{r['chat_id']}")]
        for r in recent
    ]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:refresh")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await utils.safe_edit_text(callback.message, text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.message(Command("admin_user"))
async def cmd_admin_user(message: Message, db: Database) -> None:
    if not _is_admin(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Использование: <code>/admin_user CHAT_ID</code> или <code>/admin_user @username</code>",
            parse_mode="HTML",
        )
        return
    arg = parts[1].strip()
    if arg.startswith("@") or not arg.isdigit():
        user_row = await db.get_user_by_username(arg)
        chat_id = user_row["chat_id"] if user_row else None
    else:
        chat_id = int(arg)

    if chat_id is None:
        await message.answer("Пользователь не найден.")
        return
    text, is_active = await _render_user_card(chat_id, db)
    if text is None:
        await message.answer("Пользователь не найден.")
        return
    await message.answer(text, parse_mode="HTML", reply_markup=_user_kb(chat_id, is_active))


@router.callback_query(F.data.startswith("adm:user:"))
async def cb_admin_user(callback: CallbackQuery, db: Database) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    chat_id = int(callback.data.rsplit(":", 1)[1])
    text, is_active = await _render_user_card(chat_id, db)
    if text is None:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    await utils.safe_edit_text(
        callback.message, text, parse_mode="HTML", reply_markup=_user_kb(chat_id, is_active)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:user_deactivate:"))
async def cb_user_deactivate(callback: CallbackQuery, db: Database) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    chat_id = int(callback.data.rsplit(":", 1)[1])
    await db.deactivate_user(chat_id)
    await callback.answer("Пользователь деактивирован", show_alert=True)
    text, is_active = await _render_user_card(chat_id, db)
    if text is None:
        return
    await utils.safe_edit_text(
        callback.message, text, parse_mode="HTML", reply_markup=_user_kb(chat_id, is_active)
    )


@router.callback_query(F.data.startswith("adm:user_activate:"))
async def cb_user_activate(callback: CallbackQuery, db: Database) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    chat_id = int(callback.data.rsplit(":", 1)[1])
    await db._execute(
        "UPDATE users SET is_active=1 WHERE chat_id=?", (chat_id,)
    )
    await callback.answer("Пользователь активирован", show_alert=True)
    text, is_active = await _render_user_card(chat_id, db)
    if text is None:
        return
    await utils.safe_edit_text(
        callback.message, text, parse_mode="HTML", reply_markup=_user_kb(chat_id, is_active)
    )


@router.callback_query(F.data.startswith("adm:user_debug:"))
async def cb_admin_user_debug(callback: CallbackQuery, db: Database) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    chat_id = int(callback.data.rsplit(":", 1)[1])
    text = await _render_user_debug(chat_id, db)
    if text is None:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ К пользователю", callback_data=f"adm:user:{chat_id}")
    ]])
    await utils.safe_edit_text(callback.message, text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:user_ping:"))
async def cb_admin_user_ping(callback: CallbackQuery, db: Database, metrics: Metrics) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    chat_id = int(callback.data.rsplit(":", 1)[1])
    item = utils.PendingDelivery(
        kind="broadcast",
        chat_id=chat_id,
        text=(
            "🧪 <b>Тест из админки</b>\n"
            f"<code>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</code>"
        ),
        parse_mode="HTML",
        dedupe_key=("admin_ping", callback.from_user.id, chat_id, int(time.time())),
    )
    result = await utils.send_delivery(callback.bot, item)
    if result.status == "success":
        await callback.answer("Тестовое сообщение отправлено")
        return
    if result.status == "blocked":
        await db.deactivate_user(chat_id)
        metrics.blocked_users.inc()
        await callback.answer("Пользователь заблокировал бота", show_alert=True)
        return
    await callback.answer(f"Не удалось отправить: {result.error[:80]}", show_alert=True)


# ── Metrics panel ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:metrics")
async def cb_metrics(callback: CallbackQuery, metrics: Metrics) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return

    m        = metrics.summary()
    fallback = utils.fallback_stats()
    top_cmds = "\n".join(f"  /{c}: {n}" for c, n in m["top_commands"]) or "  —"

    text = (
        f"📊 <b>Метрики (с последнего старта)</b>\n\n"
        f"⏱ Uptime: <b>{m['uptime']}</b>\n\n"
        f"<b>📨 Входящие:</b>\n"
        f"  Сообщений: {m['messages_received']}\n"
        f"  За последний час: {m['messages_per_hour']}\n"
        f"  Новых пользователей: {m['new_users']}\n\n"
        f"<b>🗄 Кэш:</b>\n"
        f"  L1 попаданий: {m['cache_l1_hits']}\n"
        f"  L2 попаданий: {m['cache_l2_hits']}\n"
        f"  Промахов (→ API): {m['cache_misses']}\n"
        f"  API запросов всего: {m['api_requests']}\n"
        f"  API ошибок: {m['api_errors']}\n"
        f"  Fallback на stale cache: {fallback['count']}\n\n"
        f"<b>🔔 Уведомления:</b>\n"
        f"  Отправлено: {m['notifications_sent']}\n"
        f"  Ошибок: {m['notifications_failed']}\n"
        f"  Дайджестов: {m['digests_sent']}\n"
        f"  Заблокировали бота: {m['blocked_users']}\n\n"
        f"<b>📋 Команды:</b>\n{top_cmds}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data="adm:refresh")
    ]])
    await utils.safe_edit_text(callback.message, text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# ── Event log ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:log")
async def cb_log(callback: CallbackQuery, db: Database) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return

    events = await db.get_recent_events(limit=20)
    if not events:
        await callback.answer("Лог пуст", show_alert=True)
        return

    lines = ["📋 <b>Последние события</b>\n"]
    for e in events:
        ts      = e["ts"][:16]
        etype   = e["event_type"]
        chat_id = e.get("chat_id", "")
        payload = e.get("payload", "")

        icon = {
            "user_created": "🆕",
            "user_blocked": "🚫",
            "api_error":    "⚡",
            "notif_sent":   "🔔",
        }.get(etype, "•")

        line = f"{icon} <code>{ts}</code> <b>{etype}</b>"
        if chat_id:
            line += f" [{chat_id}]"
        if payload:
            try:
                p = json.loads(payload)
                line += f" — {str(p)[:60]}"
            except Exception:
                pass
        lines.append(line)

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data="adm:refresh")
    ]])
    await utils.safe_edit_text(
        callback.message,
        "\n".join(lines), parse_mode="HTML", reply_markup=kb
    )
    await callback.answer()


# ── Errors panel ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:errors")
async def cb_errors(callback: CallbackQuery, metrics: Metrics) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return

    await callback.answer()

    errors = list(metrics.recent_errors)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data="adm:refresh")
    ]])
    if not errors:
        await utils.safe_edit_text(
            callback.message,
            "⚠️ <b>Ошибки</b>\n\nОшибок нет\n\n<i>Список сбрасывается при перезапуске бота.</i>",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    lines = ["⚠️ <b>Последние ошибки</b>\n"]
    for e in errors[:15]:
        ts     = e["ts"][11:16]
        source = escape(e["source"])
        err    = escape(e["error"][:120])
        lines.append(f"<code>{ts}</code> <b>{source}</b>\n  <i>{err}</i>")

    await utils.safe_edit_text(
        callback.message,
        "\n\n".join(lines), parse_mode="HTML", reply_markup=kb
    )


# ── Cache panel ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:cache")
async def cb_cache(callback: CallbackQuery, mem: MemoryCache, db: Database) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return

    l1_size  = mem.size()
    cache_rows = await db._fetchall(
        "SELECT key, cached_at FROM api_cache ORDER BY cached_at DESC"
    )

    lines = [f"🗄 <b>Кэш</b>\n\nL1 (память): <b>{l1_size}</b> записей\n\n<b>L2 (SQLite):</b>"]
    for row in cache_rows:
        key = row["key"]
        ts  = row["cached_at"][11:16]
        lines.append(f"  <code>{ts}</code> {key}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Очистить L2", callback_data="adm:cache_clear")],
        [InlineKeyboardButton(text="◀️ Назад",       callback_data="adm:refresh")],
    ])
    await utils.safe_edit_text(
        callback.message,
        "\n".join(lines) or "Кэш пуст",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data == "adm:cache_clear")
async def cb_cache_clear(
    callback: CallbackQuery, mem: MemoryCache, db: Database
) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    mem.clear()
    await db.clear_cache()
    await callback.answer("✅ Кэш очищен — следующий запрос пойдёт в API")
    await cb_cache(callback, mem, db)


# ── Cache warm-up trigger ─────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:warmup")
async def cb_warmup(
    callback: CallbackQuery, mem: MemoryCache, db: Database, runtime_state: utils.RuntimeState
) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    await callback.answer("⏳ Прогреваю кэш...")
    await utils.warm_up(mem, db, runtime_state.http_session)
    await callback.message.answer("✅ Кэш прогрет")


# ── Broadcast ─────────────────────────────────────────────────────────────────

@router.message(Command("admin_broadcast"))
async def cmd_broadcast(message: Message, db: Database, metrics: Metrics) -> None:
    if not _is_admin(message):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "Использование: <code>/admin_broadcast Текст сообщения</code>",
            parse_mode="HTML",
        )
        return

    text  = args[1]
    users = await db.get_all_users(active_only=True)
    total = len(users)

    status_msg = await message.answer(
        f"📢 Рассылка <b>{total}</b> пользователям...", parse_mode="HTML"
    )

    sent = failed = blocked = 0
    queued = 0
    bot  = message.bot
    batch_id = int(time.time())

    for user in users:
        item = utils.PendingDelivery(
            kind="broadcast",
            chat_id=user["chat_id"],
            text=text,
            parse_mode="HTML",
            dedupe_key=("broadcast", batch_id, user["chat_id"]),
        )
        result = await utils.send_delivery(bot, item)
        if result.status == "success":
            sent += 1
        elif result.status == "blocked":
            await db.deactivate_user(user["chat_id"])
            metrics.blocked_users.inc()
            blocked += 1
        else:
            item.attempts = 1
            item.last_error = result.error
            delay = result.retry_delay or 60
            if utils.delivery_queue.enqueue(item, delay_seconds=delay):
                queued += 1
            else:
                failed += 1
                metrics.notifications_failed.inc()
                metrics.record_error("broadcast", result.error or "broadcast delivery failed")
                log.error(
                    "Broadcast queue rejected for %d: %s",
                    user["chat_id"], result.error,
                )
        await asyncio.sleep(TELEGRAM_SEND_DELAY)

    await utils.safe_edit_text(
        status_msg,
        f"📢 <b>Рассылка завершена</b>\n\n"
        f"✅ Отправлено: {sent}\n"
        f"⏳ В очереди на retry: {queued}\n"
        f"🚫 Заблокировали бота: {blocked}\n"
        f"❌ Ошибок: {failed}",
        parse_mode="HTML",
    )
    log.info(
        "Broadcast done: sent=%d queued=%d blocked=%d failed=%d",
        sent, queued, blocked, failed,
    )


@router.message(Command("admin_send"))
async def cmd_admin_send(message: Message, db: Database, metrics: Metrics) -> None:
    if not _is_admin(message):
        return
    try:
        chat_id, body = _parse_admin_send_args(message.text)
    except Exception:
        await message.answer(
            "Использование: <code>/admin_send CHAT_ID текст сообщения</code>",
            parse_mode="HTML",
        )
        return

    item = utils.PendingDelivery(
        kind="broadcast",
        chat_id=chat_id,
        text=body,
        parse_mode="HTML",
        dedupe_key=("admin_send", message.from_user.id, chat_id, int(time.time())),
    )
    result = await utils.send_delivery(message.bot, item)
    if result.status == "success":
        await message.answer(f"✅ Сообщение отправлено пользователю <code>{chat_id}</code>", parse_mode="HTML")
        return
    if result.status == "blocked":
        await db.deactivate_user(chat_id)
        metrics.blocked_users.inc()
        await message.answer("🚫 Пользователь заблокировал бота.")
        return
    await message.answer(
        f"❌ Не удалось отправить пользователю <code>{chat_id}</code>: <code>{escape(result.error[:120])}</code>",
        parse_mode="HTML",
    )
