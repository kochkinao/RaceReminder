import logging
from html import escape

from aiogram import F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import utils
from config import DEFAULT_VEHICLE_CLASS_NAMES
from database import Database
from utils.cache import MemoryCache
from states import OnboardingStates

log = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery) -> None:
    await callback.answer(utils.tr(utils.UI_RU, "onboarding.checking_subscription"), show_alert=False)


@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, db: Database, mem: MemoryCache, metrics
) -> None:
    if await db.user_exists(message.chat.id):
        user = await db.get_or_create_user(message.chat.id, message.from_user.username)
        lang = utils.get_ui_lang(user)
        await message.answer(utils.tr(lang, "onboarding.welcome_back"), reply_markup=utils.main_menu(lang))
        return
    await db.create_user(message.chat.id, message.from_user.username)
    metrics.new_users.inc()
    await message.answer(
        utils.tr(utils.UI_RU, "onboarding.choose_language"),
        parse_mode="HTML",
        reply_markup=utils.ui_language_picker(),
    )
    await state.set_state(OnboardingStates.choosing_ui_language)


@router.callback_query(F.data.startswith("ui_lang:"), OnboardingStates.choosing_ui_language)
async def cb_ui_lang_chosen(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = utils.normalize_ui_lang(callback.data.split(":", 1)[1])
    await db.update_user(callback.from_user.id, ui_lang=lang)
    await callback.message.edit_text(
        utils.tr(lang, "onboarding.welcome"),
        parse_mode="HTML",
        reply_markup=utils.timezone_picker(lang=lang),
    )
    await state.set_state(OnboardingStates.choosing_timezone)
    await callback.answer()


@router.callback_query(F.data.startswith("tz_page:"))
async def cb_tz_page(callback: CallbackQuery, db: Database) -> None:
    page = int(callback.data.split(":")[1])
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    await callback.message.edit_reply_markup(reply_markup=utils.timezone_picker(page, lang=lang))
    await callback.answer()


@router.callback_query(F.data.startswith("tz:"), OnboardingStates.choosing_timezone)
async def cb_tz_chosen(
    callback: CallbackQuery, state: FSMContext, db: Database, mem: MemoryCache
) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    tz = callback.data.split(":", 1)[1]
    if tz == "manual":
        await callback.message.answer(
            utils.tr(lang, "onboarding.enter_timezone"),
            parse_mode="HTML",
        )
        await state.set_state(OnboardingStates.choosing_timezone_manual)
        await callback.answer()
        return
    await db.update_user(callback.from_user.id, timezone=tz)
    await _finish_onboarding(callback.message, state, db, mem)
    await callback.answer()


@router.message(OnboardingStates.choosing_timezone_manual)
async def msg_tz_manual(
    message: Message, state: FSMContext, db: Database, mem: MemoryCache
) -> None:
    import pytz
    user = await db.get_or_create_user(message.chat.id, message.from_user.username)
    lang = utils.get_ui_lang(user)
    tz_input = message.text.strip()
    try:
        pytz.timezone(tz_input)
    except Exception:
        await message.answer(
            utils.tr(lang, "error.unknown_timezone", value=escape(tz_input)),
            parse_mode="HTML",
            reply_markup=utils.timezone_picker(lang=lang),
        )
        return
    await db.update_user(message.chat.id, timezone=tz_input)
    await _finish_onboarding(message, state, db, mem)


async def _finish_onboarding(
    message: Message, state: FSMContext, db: Database, mem: MemoryCache
) -> None:
    await state.clear()
    chat_id = message.chat.id
    user = await db.get_or_create_user(chat_id, message.from_user.username)
    lang = utils.get_ui_lang(user)
    await message.answer(utils.tr(lang, "onboarding.subscribing"))

    subscribed: list[str] = []
    try:
        popular_series = utils.filter_series_by_group(await utils.get_all_series(mem, db), "popular")
        for s in popular_series:
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
            subs_text += f"\n  {'... и ещё' if lang == 'ru' else '... and'} {len(subscribed) - 10}"
    except Exception as exc:
        log.error("Default subscriptions failed: %s", exc)
        subs_text = utils.tr(lang, "onboarding.subscriptions_failed")

    await message.answer(
        utils.tr(lang, "onboarding.setup_done", subs_text=subs_text),
        parse_mode="HTML",
        reply_markup=utils.main_menu(lang),
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, db: Database) -> None:
    user = await db.get_or_create_user(message.chat.id, message.from_user.username)
    lang = utils.get_ui_lang(user)
    await message.answer(
        utils.tr(lang, "app.main_menu"), parse_mode="HTML", reply_markup=utils.main_menu(lang)
    )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, db: Database) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    await callback.message.edit_text(
        utils.tr(lang, "app.main_menu"), parse_mode="HTML", reply_markup=utils.main_menu(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()
