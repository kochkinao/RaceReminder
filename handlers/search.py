import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

import utils
from database import Database
from utils.cache import MemoryCache
from states import SearchStates

log = logging.getLogger(__name__)
router = Router()


# ── /search ───────────────────────────────────────────────────────────────────

@router.message(Command("search"))
async def cmd_search(
    message: Message, state: FSMContext, db: Database, mem: MemoryCache
) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        await _do_search(message, args[1].strip(), db, mem)
    else:
        await message.answer("🔍 Введите название серии или гонки:")
        await state.set_state(SearchStates.waiting_query)


@router.callback_query(F.data == "search_prompt")
async def cb_search_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer("🔍 Введите название серии или гонки:")
    await state.set_state(SearchStates.waiting_query)
    await callback.answer()


@router.message(SearchStates.waiting_query)
async def msg_search_query(
    message: Message, state: FSMContext, db: Database, mem: MemoryCache
) -> None:
    await state.clear()
    await _do_search(message, message.text.strip(), db, mem)


async def _do_search(
    message: Message, query: str, db: Database, mem: MemoryCache
) -> None:
    low        = query.lower()
    all_series = await utils.get_all_series(mem, db)

    matches = [
        s for s in all_series
        if low in s.get("name", "").lower() or low in s.get("description", "").lower()
    ]

    if not matches:
        await message.answer(f"😕 Ничего не найдено по запросу «{query}»")
        return

    if len(matches) == 1:
        await _send_series_card(message, matches[0], db)
        return

    btns = [
        [InlineKeyboardButton(
            text=s.get("name", "?")[:50],
            callback_data=f"series_info:{s['id']}",
        )]
        for s in matches[:20]
    ]
    await message.answer(
        f"🔍 Найдено {len(matches)} серий по запросу «{query}»:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
    )


async def _send_series_card(message: Message, series: dict, db: Database) -> None:
    name = series.get("name", "")
    info = utils.get_series_info(name)
    if info:
        text = utils.format_card(name, info)
    else:
        classes = ", ".join(vc.get("name", "") for vc in series.get("vehicleClasses", []))
        text = f"🏎️ <b>{name}</b>\n\n{series.get('description', '')}"
        if classes:
            text += f"\n\n🏷️ {classes}"
        if link := series.get("infoLink"):
            text += f"\n🌐 <a href='{link}'>Официальный сайт</a>"

    is_sub   = await db.is_subscribed(message.chat.id, "series", series["id"])
    sub_text = "❌ Отписаться" if is_sub else "✅ Подписаться"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=sub_text,
            callback_data=utils.SubToggleCD(type="series", ref_id=series["id"], page=0).pack(),
        ),
        InlineKeyboardButton(text="◀️ Назад", callback_data="subs_menu"),
    ]])
    await message.answer(
        text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True
    )


# ── /kb — knowledge base ──────────────────────────────────────────────────────

@router.message(Command("kb"))
async def cmd_kb(message: Message) -> None:
    await message.answer(
        "📚 <b>База знаний</b>\nВыберите серию:",
        parse_mode="HTML",
        reply_markup=utils.kb_menu(utils.SERIES_KB),
    )


@router.callback_query(F.data == "kb_menu")
async def cb_kb_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "📚 <b>База знаний</b>\nВыберите серию:",
        parse_mode="HTML",
        reply_markup=utils.kb_menu(utils.SERIES_KB),
    )
    await callback.answer()


@router.callback_query(utils.KbShowCD.filter())
async def cb_kb_show(
    callback: CallbackQuery,
    callback_data: utils.KbShowCD,
    db: Database,
    mem: MemoryCache,
) -> None:
    name = callback_data.name
    info = utils.SERIES_KB.get(name)
    if not info:
        await callback.answer("Серия не найдена")
        return

    text    = utils.format_card(name, info)
    similar = info.get("similar", [])

    btns: list[list[InlineKeyboardButton]] = []

    similar_row = [
        InlineKeyboardButton(text=f"→ {s}", callback_data=utils.KbShowCD(name=s).pack())
        for s in similar[:3]                           # type: ignore[union-attr]
        if s in utils.SERIES_KB
    ]
    if similar_row:
        btns.append(similar_row)

    all_series = await utils.get_all_series(mem, db)
    matched    = next(
        (s for s in all_series if name.lower() in s.get("name", "").lower()), None
    )
    if matched:
        is_sub   = await db.is_subscribed(callback.from_user.id, "series", matched["id"])
        sub_text = "❌ Отписаться" if is_sub else "✅ Подписаться"
        btns.append([InlineKeyboardButton(
            text=sub_text,
            callback_data=utils.SubToggleCD(type="series", ref_id=matched["id"], page=0).pack(),
        )])

    btns.append([InlineKeyboardButton(text="◀️ База знаний", callback_data="kb_menu")])

    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
        disable_web_page_preview=True,
    )
    await callback.answer()
