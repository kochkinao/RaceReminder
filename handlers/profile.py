import json
import logging
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import utils
from database import Database
from states import ProfileStates

log = logging.getLogger(__name__)
router = Router()

_TOGGLE_FIELDS = {
    "digest_enabled", "show_no_broadcast", "quiet_enabled",
    "show_qualifying", "show_practice",
    "notify_3days", "notify_1day", "notify_1hour", "notify_start",
}


async def _show_profile(target: Message | CallbackQuery, db: Database) -> None:
    chat_id = target.from_user.id
    user = await db.get_or_create_user(chat_id)
    lang = utils.get_ui_lang(user)

    langs = json.loads(user.get("preferred_langs", '["English"]'))
    text = (
        f"{utils.tr(lang, 'profile.title')}\n\n"
        f"{utils.tr(
            lang,
            'profile.summary',
            timezone=user['timezone'],
            langs=', '.join(langs),
            digest_state=utils.bool_text(lang, bool(user['digest_enabled'])),
            digest_time=user['digest_time'],
            quiet_state=utils.bool_text(lang, bool(user['quiet_enabled'])),
            quiet_start=user['quiet_start'],
            quiet_end=user['quiet_end'],
        )}"
    )
    kb = utils.profile_menu(user, lang)

    match target:
        case CallbackQuery():
            await target.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
            await target.answer()
        case Message():
            await target.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("profile"))
async def cmd_profile(message: Message, db: Database) -> None:
    await _show_profile(message, db)


@router.callback_query(F.data == "profile_menu")
async def cb_profile_menu(callback: CallbackQuery, db: Database) -> None:
    await _show_profile(callback, db)


# ── Toggle boolean settings ───────────────────────────────────────────────────

@router.callback_query(utils.ProfileToggleCD.filter())
async def cb_toggle(
    callback: CallbackQuery,
    callback_data: utils.ProfileToggleCD,
    db: Database,
) -> None:
    field = callback_data.field
    if field not in _TOGGLE_FIELDS:
        user = await db.get_or_create_user(callback.from_user.id)
        await callback.answer(utils.tr(utils.get_ui_lang(user), "generic.unknown_setting"))
        return
    user = await db.get_or_create_user(callback.from_user.id)
    await db.update_user(callback.from_user.id, **{field: 0 if user[field] else 1})
    await _show_profile(callback, db)


# ── Language picker ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile:langs")
async def cb_langs(callback: CallbackQuery, db: Database) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    current = json.loads(user.get("preferred_langs", '["English"]'))
    await callback.message.edit_text(
        utils.tr(lang, "profile.broadcast_languages_title"),
        parse_mode="HTML",
        reply_markup=utils.lang_picker(current, lang),
    )
    await callback.answer()


@router.callback_query(utils.LangToggleCD.filter())
async def cb_toggle_lang(
    callback: CallbackQuery,
    callback_data: utils.LangToggleCD,
    db: Database,
) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    current: list[str] = json.loads(user.get("preferred_langs", '["English"]'))
    lang_id = callback_data.lang_id

    if lang_id in current:
        current.remove(lang_id)
    else:
        current.append(lang_id)
    if not current:
        current = ["English"]

    await db.update_user(callback.from_user.id, preferred_langs=json.dumps(current))
    await callback.message.edit_reply_markup(reply_markup=utils.lang_picker(current, lang))
    await callback.answer()


# ── Timezone ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile:tz")
async def cb_tz(callback: CallbackQuery, db: Database) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    await callback.message.answer(utils.tr(lang, "profile.choose_timezone"), reply_markup=utils.timezone_picker(lang=lang))
    await callback.answer()


@router.callback_query(F.data.startswith("tz:"))
async def cb_set_tz(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    tz = callback.data.split(":", 1)[1]
    if tz == "manual":
        await callback.message.answer(
            utils.tr(lang, "onboarding.enter_timezone"), parse_mode="HTML"
        )
        await state.set_state(ProfileStates.editing_timezone_manual)
        await callback.answer()
        return
    await db.update_user(callback.from_user.id, timezone=tz)
    await callback.answer(f"✅ {tz}")
    await _show_profile(callback, db)


@router.message(ProfileStates.editing_timezone_manual)
async def msg_tz_manual(message: Message, state: FSMContext, db: Database) -> None:
    import pytz
    user = await db.get_or_create_user(message.chat.id, message.from_user.username)
    lang = utils.get_ui_lang(user)
    tz_input = message.text.strip()
    try:
        pytz.timezone(tz_input)
    except Exception:
        await message.answer(utils.tr(lang, "profile.invalid_timezone"))
        return
    await db.update_user(message.chat.id, timezone=tz_input)
    await state.clear()
    await message.answer(
        utils.tr(lang, "profile.timezone_updated", value=escape(tz_input)),
        parse_mode="HTML",
    )
    await _show_profile(message, db)


# ── Digest time ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile:digest_time")
async def cb_digest_time(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    await callback.message.answer(
        utils.tr(lang, "profile.digest_time_prompt"),
        parse_mode="HTML",
    )
    await state.set_state(ProfileStates.editing_digest_time)
    await callback.answer()


@router.message(ProfileStates.editing_digest_time)
async def msg_digest_time(message: Message, state: FSMContext, db: Database) -> None:
    user = await db.get_or_create_user(message.chat.id, message.from_user.username)
    lang = utils.get_ui_lang(user)
    t = message.text.strip()
    try:
        h, m = t.split(":")
        assert 0 <= int(h) <= 23 and 0 <= int(m) <= 59
        time_str = f"{int(h):02d}:{int(m):02d}"
    except Exception:
        await message.answer(utils.tr(lang, "profile.invalid_time"), parse_mode="HTML")
        return
    await db.update_user(message.chat.id, digest_time=time_str)
    await state.clear()
    await message.answer(utils.tr(lang, "profile.digest_time_updated", value=time_str), parse_mode="HTML")


# ── Quiet hours ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile:quiet_hours")
async def cb_quiet_hours(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    await callback.message.answer(
        utils.tr(lang, "profile.quiet_hours_prompt"),
        parse_mode="HTML",
    )
    await state.set_state(ProfileStates.editing_quiet_hours)
    await callback.answer()


@router.message(ProfileStates.editing_quiet_hours)
async def msg_quiet_hours(message: Message, state: FSMContext, db: Database) -> None:
    user = await db.get_or_create_user(message.chat.id, message.from_user.username)
    lang = utils.get_ui_lang(user)
    try:
        parts = message.text.strip().split()
        start, end = int(parts[0]), int(parts[1])
        assert 0 <= start <= 23 and 0 <= end <= 23
    except Exception:
        await message.answer(utils.tr(lang, "profile.invalid_quiet_hours"), parse_mode="HTML")
        return
    await db.update_user(message.chat.id, quiet_start=start, quiet_end=end)
    await state.clear()
    await message.answer(utils.tr(lang, "profile.quiet_hours_updated", start=start, end=end))
