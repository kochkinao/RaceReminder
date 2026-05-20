import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN, LOG_LEVEL
from database import Database
from utils.cache import MemoryCache
from middlewares import DatabaseMiddleware, SubscriptionMiddleware, ThrottlingMiddleware
from scheduler import make_scheduler
import utils
import handlers

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

_COMMANDS = [
    BotCommand(command="start",         description="🏁 Начать / главное меню"),
    BotCommand(command="menu",          description="📋 Меню"),
    BotCommand(command="today",         description="📅 Гонки сегодня"),
    BotCommand(command="week",          description="📆 Гонки на неделю"),
    BotCommand(command="history",       description="📖 Прошедшие гонки"),
    BotCommand(command="subscriptions", description="⭐ Подписки"),
    BotCommand(command="search",        description="🔍 Поиск серий и гонок"),
    BotCommand(command="kb",            description="📚 База знаний"),
    BotCommand(command="profile",       description="⚙️ Личный кабинет"),
]


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в .env")

    # ── Infrastructure ────────────────────────────────────────────────────────
    db  = Database()
    mem = MemoryCache()

    await db.connect()
    log.info("Database ready")

    # Warm-up before first user request:
    # fills L1+L2 cache, prebuilds session banners
    await utils.warm_up(mem, db)

    # ── Bot & Dispatcher ──────────────────────────────────────────────────────
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp  = Dispatcher(storage=MemoryStorage())

    # Middlewares — order matters:
    # 1. DatabaseMiddleware injects db+mem into every handler
    # 2. ThrottlingMiddleware blocks message spam
    # 3. SubscriptionMiddleware checks channel gate (no-op if CHANNEL_ID unset)
    dp.update.middleware(DatabaseMiddleware(db, mem))
    dp.message.middleware(ThrottlingMiddleware())
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    dp.include_routers(
        handlers.start.router,
        handlers.profile.router,
        handlers.subscriptions.router,
        handlers.digest.router,
        handlers.search.router,
    )

    await bot.set_my_commands(_COMMANDS)
    log.info("Commands registered")

    # ── Scheduler ─────────────────────────────────────────────────────────────
    scheduler = make_scheduler(bot, db, mem)
    scheduler.start()
    log.info("Scheduler started")

    # ── Polling ───────────────────────────────────────────────────────────────
    log.info("Polling started")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        log.info("Shutting down...")
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await db.close()          # flush persistent connection
        log.info("Shutdown complete")


def main_sync() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
