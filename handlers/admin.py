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
from datetime import datetime, timezone

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
from utils.cache import MemoryCache
from utils.metrics import Metrics

log = logging.getLogger(__name__)
router = Router()


# ── Guard filter ──────────────────────────────────────────────────────────────

def _is_admin(message: Message) -> bool:
    return message.from_user.id in ADMIN_IDS


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

async def _dashboard_text(db: Database, mem: MemoryCache, metrics: Metrics) -> str:
    stats = await db.get_stats()
    m     = metrics.summary()
    now   = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    cache_total = m["cache_l1_hits"] + m["cache_l2_hits"] + m["cache_misses"]
    l1_pct = int(m["cache_l1_hits"] / cache_total * 100) if cache_total else 0
    l2_pct = int(m["cache_l2_hits"] / cache_total * 100) if cache_total else 0

    top_cmd = "\n".join(
        f"  /{cmd}: {n}" for cmd, n in m["top_commands"][:5]
    ) or "  —"

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
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message, db: Database, mem: MemoryCache, metrics: Metrics) -> None:
    if not _is_admin(message):
        return
    text = await _dashboard_text(db, mem, metrics)
    await message.answer(text, parse_mode="HTML", reply_markup=_admin_kb())


@router.callback_query(F.data == "adm:refresh")
async def cb_refresh(
    callback: CallbackQuery, db: Database, mem: MemoryCache, metrics: Metrics
) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    text = await _dashboard_text(db, mem, metrics)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_admin_kb())
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
        f"  {r['created_at'][:16]} — @{r['username'] or r['chat_id']}"
        for r in recent
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
        f"<b>🕐 Последние регистрации:</b>\n{recent_text}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data="adm:refresh")
    ]])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# ── Metrics panel ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:metrics")
async def cb_metrics(callback: CallbackQuery, metrics: Metrics) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return

    m        = metrics.summary()
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
        f"  API ошибок: {m['api_errors']}\n\n"
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
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
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
    await callback.message.edit_text(
        "\n".join(lines), parse_mode="HTML", reply_markup=kb
    )
    await callback.answer()


# ── Errors panel ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:errors")
async def cb_errors(callback: CallbackQuery, metrics: Metrics) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return

    errors = list(metrics.recent_errors)
    if not errors:
        await callback.answer("Ошибок нет 🎉", show_alert=True)
        return

    lines = ["⚠️ <b>Последние ошибки</b>\n"]
    for e in errors[:15]:
        ts     = e["ts"][11:16]
        source = e["source"]
        err    = e["error"][:120]
        lines.append(f"<code>{ts}</code> <b>{source}</b>\n  <i>{err}</i>")

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data="adm:refresh")
    ]])
    await callback.message.edit_text(
        "\n\n".join(lines), parse_mode="HTML", reply_markup=kb
    )
    await callback.answer()


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
    await callback.message.edit_text(
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
    callback: CallbackQuery, mem: MemoryCache, db: Database
) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    await callback.answer("⏳ Прогреваю кэш...")
    import utils
    await utils.warm_up(mem, db)
    await callback.answer("✅ Кэш прогрет")


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
    bot  = message.bot

    for user in users:
        try:
            await bot.send_message(
                user["chat_id"], text, parse_mode="HTML"
            )
            sent += 1
        except Exception as exc:
            err = str(exc).lower()
            if "forbidden" in err or "blocked" in err or "deactivated" in err:
                await db.deactivate_user(user["chat_id"])
                metrics.blocked_users.inc()
                blocked += 1
            else:
                failed += 1
        await asyncio.sleep(TELEGRAM_SEND_DELAY)

    await status_msg.edit_text(
        f"📢 <b>Рассылка завершена</b>\n\n"
        f"✅ Отправлено: {sent}\n"
        f"🚫 Заблокировали бота: {blocked}\n"
        f"❌ Ошибок: {failed}",
        parse_mode="HTML",
    )
    log.info(
        "Broadcast done: sent=%d blocked=%d failed=%d", sent, blocked, failed
    )
