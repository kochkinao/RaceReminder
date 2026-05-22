import logging
from html import escape

from aiogram import F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import utils
from config import DEFAULT_SERIES_NAMES, DEFAULT_VEHICLE_CLASS_NAMES
from database import Database
from utils.cache import MemoryCache
from states import OnboardingStates

log = logging.getLogger(__name__)
router = Router()

_WELCOME = """\
🏁 <b>Добро пожаловать в RaceDay Bot!</b>

Я слежу за гоночным календарём и присылаю уведомления о гонках.

<b>Что умею:</b>
• 📅 Еженедельный дайджест по понедельникам
• 🔔 Напоминания за 3 дня, сутки и час до старта
• 📺 Ссылки на трансляции с фильтром по языку
• 📚 База знаний о популярных сериях
• 🔍 Поиск гонок и серий

По умолчанию подписка на F1, WEC, IMSA, WRC и другие топ-серии.

Для начала выберите <b>часовой пояс</b>:
"""


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery) -> None:
    await callback.answer("Проверяем подписку...", show_alert=False)


@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, db: Database, mem: MemoryCache, metrics
) -> None:
    if await db.user_exists(message.chat.id):
        await message.answer("👋 С возвращением!", reply_markup=utils.main_menu())
        return
    await db.create_user(message.chat.id, message.from_user.username)
    metrics.new_users.inc()
    await message.answer(_WELCOME, parse_mode="HTML", reply_markup=utils.timezone_picker())
    await state.set_state(OnboardingStates.choosing_timezone)


@router.callback_query(F.data.startswith("tz_page:"))
async def cb_tz_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=utils.timezone_picker(page))
    await callback.answer()


@router.callback_query(F.data.startswith("tz:"), OnboardingStates.choosing_timezone)
async def cb_tz_chosen(
    callback: CallbackQuery, state: FSMContext, db: Database, mem: MemoryCache
) -> None:
    tz = callback.data.split(":", 1)[1]
    if tz == "manual":
        await callback.message.answer(
            "Введите ваш часовой пояс, например: <code>Europe/Berlin</code>",
            parse_mode="HTML",
        )
        await state.set_state(OnboardingStates.choosing_timezone_manual)
        await callback.answer()
        return
    await db.update_user(callback.message.chat.id, timezone=tz)
    await _finish_onboarding(callback.message, state, db, mem)
    await callback.answer()


@router.message(OnboardingStates.choosing_timezone_manual)
async def msg_tz_manual(
    message: Message, state: FSMContext, db: Database, mem: MemoryCache
) -> None:
    import pytz
    tz_input = message.text.strip()
    try:
        pytz.timezone(tz_input)
    except Exception:
        await message.answer(
            f"❌ Неизвестный часовой пояс <code>{escape(tz_input)}</code>. Попробуйте снова.",
            parse_mode="HTML",
            reply_markup=utils.timezone_picker(),
        )
        return
    await db.update_user(message.chat.id, timezone=tz_input)
    await _finish_onboarding(message, state, db, mem)


async def _finish_onboarding(
    message: Message, state: FSMContext, db: Database, mem: MemoryCache
) -> None:
    await state.clear()
    chat_id = message.chat.id
    await message.answer("⏳ Подписываю на популярные серии...")

    subscribed: list[str] = []
    try:
        for s in await utils.get_all_series(mem, db):
            if s.get("name") in DEFAULT_SERIES_NAMES:
                await db.add_subscription(chat_id, "series", s["id"], s.get("name", ""))
                subscribed.append(s["name"])
        if not subscribed:
            for vc in await utils.get_all_vehicle_classes(mem, db):
                if vc.get("name") in DEFAULT_VEHICLE_CLASS_NAMES:
                    await db.add_subscription(
                        chat_id, "vehicle_class", vc["id"], vc.get("name", "")
                    )
        subs_text = "\n".join(f"  ✅ {n}" for n in subscribed[:10])
        if len(subscribed) > 10:
            subs_text += f"\n  ... и ещё {len(subscribed) - 10}"
    except Exception as exc:
        log.error("Default subscriptions failed: %s", exc)
        subs_text = "  (не удалось загрузить список серий)"

    await message.answer(
        f"✅ <b>Настройка завершена!</b>\n\nВы подписаны на:\n{subs_text}\n\n"
        f"Используйте /menu для навигации.",
        parse_mode="HTML",
        reply_markup=utils.main_menu(),
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    await message.answer(
        "🏁 <b>Главное меню</b>", parse_mode="HTML", reply_markup=utils.main_menu()
    )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🏁 <b>Главное меню</b>", parse_mode="HTML", reply_markup=utils.main_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()
