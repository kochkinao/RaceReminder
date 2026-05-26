"""
Entry point.

Startup sequence:
  1. Logging (with admin alerts via Telegram)
  2. Database (persistent connection)
  3. Cache warm-up (API → L2 → L1)
  4. Bot + Dispatcher + Middlewares
  5. Scheduler (jobs)
  6. Polling

Shutdown (Ctrl+C / SIGTERM):
  1. Scheduler.shutdown
  2. bot.session.close
  3. db.close (flush WAL)
"""
import asyncio
import logging

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

import handlers
from config import ADMIN_IDS, BOT_TOKEN, LOG_LEVEL
from database import Database
from middlewares import (
    DatabaseMiddleware,
    MetricsMiddleware,
    SubscriptionMiddleware,
    ThrottlingMiddleware,
)
from scheduler import make_scheduler
from utils.cache import MemoryCache
from utils.logging_setup import setup_logging
from utils.metrics import Metrics

import utils


async def main() -> None:
    # ── 1. Logging ────────────────────────────────────────────────────────────
    admin_handler = setup_logging(LOG_LEVEL, ADMIN_IDS)
    log = logging.getLogger(__name__)
    log.info("Starting RaceReminder Bot")

    # ── 2. Infrastructure ─────────────────────────────────────────────────────
    db      = Database()
    mem     = MemoryCache()
    metrics = Metrics()
    state   = utils.RuntimeState()
    http_session = aiohttp.ClientSession()
    state.http_session = http_session

    await db.connect()
    state.mark_db_connected()

    # ── 3. Cache warm-up ──────────────────────────────────────────────────────
    state.last_warmup_ok = await utils.warm_up(mem, db, http_session)

    # ── 4. Bot + Dispatcher ───────────────────────────────────────────────────
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp  = Dispatcher()

    # Wire bot into admin alert handler so errors go to Telegram
    loop = asyncio.get_running_loop()
    admin_handler.set_bot(bot, loop)
    state.mark_bot_started()
    log.info("Admin alert handler connected (IDs: %s)", ADMIN_IDS)

    # Middlewares — order matters
    dp.update.middleware(DatabaseMiddleware(db, mem))    # injects db, mem; touches last_seen
    dp.update.middleware(MetricsMiddleware(metrics))     # injects metrics; counts messages
    dp.message.middleware(ThrottlingMiddleware())        # 1 msg/sec per user
    dp.message.middleware(SubscriptionMiddleware())      # channel gate (optional)

    # Routers
    dp.include_router(handlers.start.router)
    dp.include_router(handlers.profile.router)
    dp.include_router(handlers.subscriptions.router)
    dp.include_router(handlers.digest.router)
    dp.include_router(handlers.search.router)
    dp.include_router(handlers.session_details.router)
    dp.include_router(handlers.rscg.router)
    dp.include_router(handlers.admin.router)

    # ── 5. Scheduler ─────────────────────────────────────────────────────────
    scheduler = make_scheduler(bot, db, mem, metrics, state)
    scheduler.start()
    state.mark_scheduler_started()
    log.info("Scheduler started")

    # Alert admins that bot started
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "✅ <b>RaceReminder Bot запущен</b>\n"
                f"L1 записей: {mem.size()}",
                parse_mode="HTML",
            )
        except Exception:
            pass

    # ── 6. Polling ────────────────────────────────────────────────────────────
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), runtime_state=state)
    finally:
        scheduler.shutdown(wait=False)

        # Alert admins about shutdown
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, "🔴 <b>RaceReminder Bot остановлен</b>", parse_mode="HTML")
            except Exception:
                pass

        await http_session.close()
        await bot.session.close()
        await db.close()


def main_sync() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
