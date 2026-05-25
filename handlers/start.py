import logging
from html import escape

from aiogram import F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import utils
from config import DEFAULT_ONBOARDING_SERIES_NAMES, DEFAULT_VEHICLE_CLASS_NAMES
from database import Database
from utils.cache import MemoryCache
from states import OnboardingStates

log = logging.getLogger(__name__)
router = Router()


def _is_onboarding_default_series(name: str) -> bool:
    lowered = (name or "").strip().lower()
    return (
        lowered == "formula 1"
        or "world endurance championship" in lowered
        or lowered.startswith("imsa ")
        or lowered == "imsa"
    )


async def _main_menu_text(db: Database, chat_id: int, lang: str) -> str:
    subs = await db.get_subscriptions(chat_id)
    if subs:
        return utils.tr(lang, "app.main_menu")
    return utils.tr(lang, "app.main_menu_empty")


async def _show_help(target: Message | CallbackQuery, db: Database) -> None:
    chat_id = target.from_user.id if isinstance(target, CallbackQuery) else target.chat.id
    user = await db.get_or_create_user(chat_id, getattr(getattr(target, "from_user", None), "username", None))
    lang = utils.get_ui_lang(user)
    text = f"{utils.tr(lang, 'help.title')}\n\n{utils.tr(lang, 'help.body')}"
    kb = utils.back_to_menu(lang)
    if isinstance(target, CallbackQuery):
        await utils.safe_edit_text(target.message, text, parse_mode="HTML", reply_markup=kb)
        await target.answer()
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery, db: Database) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    await callback.answer(utils.tr(lang, "onboarding.checking_subscription"), show_alert=False)


@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, db: Database, mem: MemoryCache, metrics, runtime_state
) -> None:
    if await db.user_exists(message.chat.id):
        user = await db.get_or_create_user(message.chat.id, message.from_user.username)
        lang = utils.get_ui_lang(user)
        await message.answer(
            f"{utils.tr(lang, 'onboarding.welcome_back')}\n\n{await _main_menu_text(db, message.chat.id, lang)}",
            parse_mode="HTML",
            reply_markup=utils.main_menu(lang),
        )
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
    await utils.safe_edit_text(
        callback.message,
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
    await utils.safe_edit_reply_markup(callback.message, reply_markup=utils.timezone_picker(page, lang=lang))
    await callback.answer()


@router.callback_query(F.data.startswith("tz:"), OnboardingStates.choosing_timezone)
async def cb_tz_chosen(
    callback: CallbackQuery, state: FSMContext, db: Database, mem: MemoryCache, runtime_state
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
    await state.clear()
    await _finish_onboarding(callback.message, state, db, mem, runtime_state)
    await callback.answer()


@router.message(OnboardingStates.choosing_timezone_manual)
async def msg_tz_manual(
    message: Message, state: FSMContext, db: Database, mem: MemoryCache, runtime_state
) -> None:
    user = await db.get_or_create_user(message.chat.id, message.from_user.username)
    lang = utils.get_ui_lang(user)
    tz_input = message.text.strip()
    matches = utils.resolve_timezone_input(tz_input)
    if not matches:
        await message.answer(
            utils.tr(lang, "error.unknown_timezone", value=escape(tz_input)),
            parse_mode="HTML",
            reply_markup=utils.timezone_picker(lang=lang),
        )
        return
    if len(matches) > 1:
        await message.answer(
            utils.tr(lang, "profile.ambiguous_timezone"),
            reply_markup=utils.timezone_matches_picker(matches, lang=lang),
        )
        return
    await db.update_user(message.chat.id, timezone=matches[0])
    await _finish_onboarding(message, state, db, mem, runtime_state)


async def _finish_onboarding(
    message: Message, state: FSMContext, db: Database, mem: MemoryCache, runtime_state
) -> None:
    await state.clear()
    chat_id = message.chat.id
    user = await db.get_or_create_user(chat_id, message.from_user.username)
    lang = utils.get_ui_lang(user)
    await message.answer(utils.tr(lang, "onboarding.subscribing"))

    subscribed: list[str] = []
    try:
        all_series = await utils.get_all_series(mem, db, runtime_state.http_session)
        onboarding_series = [s for s in all_series if _is_onboarding_default_series(s.get("name", ""))]
        onboarding_series.sort(
            key=lambda item: next(
                (
                    idx for idx, label in enumerate(DEFAULT_ONBOARDING_SERIES_NAMES)
                    if (
                        label == "Formula 1" and item.get("name", "") == "Formula 1"
                    ) or (
                        label == "FIA World Endurance Championship" and "world endurance championship" in item.get("name", "").lower()
                    ) or (
                        label == "IMSA" and item.get("name", "").lower().startswith("imsa")
                    )
                ),
                999,
            )
        )
        for s in onboarding_series:
            await db.add_subscription(chat_id, "series", s["id"], s.get("name", ""))
            subscribed.append(utils.display_series_name(s["name"]))
        if not subscribed:
            for vc in await utils.get_all_vehicle_classes(mem, db, runtime_state.http_session):
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
        await _main_menu_text(db, message.chat.id, lang),
        parse_mode="HTML",
        reply_markup=utils.main_menu(lang),
    )


@router.message(Command("help"))
async def cmd_help(message: Message, db: Database) -> None:
    await _show_help(message, db)


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, db: Database) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    await utils.safe_edit_text(
        callback.message,
        await _main_menu_text(db, callback.from_user.id, lang),
        parse_mode="HTML",
        reply_markup=utils.main_menu(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery, db: Database) -> None:
    await _show_help(callback, db)


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()
