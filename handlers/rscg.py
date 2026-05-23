import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import utils
from database import Database
from utils.cache import MemoryCache

log = logging.getLogger(__name__)
router = Router()

_RSCG_REF_ID = "rscg"
_RSCG_REF_NAME = "СМП РСКГ"


async def _show_rscg_list(
    target: Message | CallbackQuery,
    db: Database,
    mem: MemoryCache,
    http_session,
    *,
    answer_callback: bool = True,
) -> None:
    chat_id = target.from_user.id if isinstance(target, CallbackQuery) else target.chat.id
    user = await db.get_or_create_user(chat_id, getattr(getattr(target, "from_user", None), "username", None))
    lang = utils.get_ui_lang(user)
    stages = await utils.get_rscg_stages(mem, db, http_session)
    if not stages:
        text = utils.tr(lang, "rscg.empty")
        if isinstance(target, CallbackQuery):
            await utils.safe_edit_text(target.message, text, parse_mode="HTML", reply_markup=utils.back_to_menu(lang))
            if answer_callback:
                await target.answer()
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=utils.back_to_menu(lang))
        return

    is_subscribed = await db.is_subscribed(chat_id, "rscg", _RSCG_REF_ID)
    text = utils.tr(lang, "rscg.list_title")
    kb = utils.rscg_list_kb(stages, is_subscribed, lang=lang)

    if isinstance(target, CallbackQuery):
        await utils.safe_edit_text(target.message, text, parse_mode="HTML", reply_markup=kb)
        if answer_callback:
            await target.answer()
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)


async def _show_rscg_stage(
    callback: CallbackQuery,
    stage_id: int,
    db: Database,
    mem: MemoryCache,
    http_session,
    *,
    answer_callback: bool = True,
) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    stages = await utils.get_rscg_stages(mem, db, http_session)
    stage = next((item for item in stages if item.id == stage_id), None)
    if not stage:
        if answer_callback:
            await callback.answer(utils.tr(lang, "rscg.stage_not_found"), show_alert=True)
        return

    is_subscribed = await db.is_subscribed(callback.from_user.id, "rscg", _RSCG_REF_ID)
    text = utils.rscg_stage_card(stage, user)
    kb = utils.rscg_stage_kb(stage, is_subscribed, lang=lang)
    await utils.safe_edit_text(callback.message, text, parse_mode="HTML", reply_markup=kb)
    if answer_callback:
        await callback.answer()


@router.message(Command("rscg"))
async def cmd_rscg(message: Message, db: Database, mem: MemoryCache, runtime_state) -> None:
    await _show_rscg_list(message, db, mem, runtime_state.http_session)


@router.callback_query(utils.RscgCD.filter(F.action == "list"))
async def cb_rscg_list(callback: CallbackQuery, db: Database, mem: MemoryCache, runtime_state) -> None:
    await callback.answer()
    await _show_rscg_list(callback, db, mem, runtime_state.http_session, answer_callback=False)


@router.callback_query(utils.RscgCD.filter(F.action == "stage"))
async def cb_rscg_stage(
    callback: CallbackQuery,
    callback_data: utils.RscgCD,
    db: Database,
    mem: MemoryCache,
    runtime_state,
) -> None:
    await callback.answer()
    await _show_rscg_stage(
        callback,
        callback_data.stage_id,
        db,
        mem,
        runtime_state.http_session,
        answer_callback=False,
    )


@router.callback_query(utils.RscgCD.filter(F.action == "sub"))
async def cb_rscg_subscribe(callback: CallbackQuery, db: Database, mem: MemoryCache, runtime_state) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    await db.add_subscription(callback.from_user.id, "rscg", _RSCG_REF_ID, _RSCG_REF_NAME)
    await _show_rscg_list(callback, db, mem, runtime_state.http_session, answer_callback=False)
    await callback.answer(utils.tr(lang, "rscg.subscribed"))


@router.callback_query(utils.RscgCD.filter(F.action == "unsub"))
async def cb_rscg_unsubscribe(callback: CallbackQuery, db: Database, mem: MemoryCache, runtime_state) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    await db.remove_subscription(callback.from_user.id, "rscg", _RSCG_REF_ID)
    await _show_rscg_list(callback, db, mem, runtime_state.http_session, answer_callback=False)
    await callback.answer(utils.tr(lang, "rscg.unsubscribed"))
