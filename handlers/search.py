import logging
<<<<<<< HEAD
import re
import unicodedata

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import utils
from config import SEARCH_ALIASES
from database import Database
from utils.cache import MemoryCache

log    = logging.getLogger(__name__)
router = Router()


# ── Search normalization ──────────────────────────────────────────────────────

def _normalize(s: str) -> str:
    """Lowercase, strip diacritics/umlauts, collapse non-alphanumeric to spaces."""
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("ß", "ss")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def _normalize_compact(s: str) -> str:
    return _normalize(s).replace(" ", "")


def _search_match(query: str, target: str) -> bool:
    """True if normalized query substring-matches normalized target (or vice-versa).
    Handles umlauts (Nurburgring→Nürburgring), missing spaces (formula1→Formula 1),
    mixed case, and dashes vs spaces.
    """
    nq, nt = _normalize(query), _normalize(target)
    cq, ct = _normalize_compact(query), _normalize_compact(target)
    return nq in nt or nt in nq or cq in ct or ct in cq


# ── Helpers ───────────────────────────────────────────────────────────────────
=======

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

>>>>>>> 1f73ea54b9272d81ba0ddf95726a9bd145218694

def _kb_sub_callback(series_id: str) -> str:
    return f"kb_sub:{series_id}"


async def _build_kb_card(
    user_id: int,
    name: str,
    db: Database,
    mem: MemoryCache,
) -> tuple[str, InlineKeyboardMarkup]:
    info = utils.SERIES_KB.get(name)
    if not info:
        raise ValueError("Серия не найдена")

<<<<<<< HEAD
    text    = utils.format_card(name, info)
=======
    text = utils.format_card(name, info)
>>>>>>> 1f73ea54b9272d81ba0ddf95726a9bd145218694
    similar = info.get("similar", [])
    btns: list[list[InlineKeyboardButton]] = []

    similar_row = [
        InlineKeyboardButton(text=f"→ {s}", callback_data=utils.KbShowCD(name=s).pack())
        for s in similar[:3]
        if s in utils.SERIES_KB
    ]
    if similar_row:
        btns.append(similar_row)

    all_series = await utils.get_all_series(mem, db)
    matched = next(
        (s for s in all_series if name.lower() in s.get("name", "").lower()), None
    )
    if matched:
<<<<<<< HEAD
        is_sub   = await db.is_subscribed(user_id, "series", matched["id"])
=======
        is_sub = await db.is_subscribed(user_id, "series", matched["id"])
>>>>>>> 1f73ea54b9272d81ba0ddf95726a9bd145218694
        sub_text = "❌ Отписаться" if is_sub else "✅ Подписаться"
        btns.append([InlineKeyboardButton(
            text=sub_text,
            callback_data=_kb_sub_callback(matched["id"]),
        )])

    btns.append([InlineKeyboardButton(text="◀️ База знаний", callback_data="kb_menu")])
    return text, InlineKeyboardMarkup(inline_keyboard=btns)


<<<<<<< HEAD
# ── Search ────────────────────────────────────────────────────────────────────

@router.message(F.text.startswith("🔍"))
async def msg_search_btn(message: Message, db: Database, mem: MemoryCache) -> None:
    await _show_search_prompt(message)


async def _show_search_prompt(target: Message) -> None:
    await target.answer(
        "🔍 <b>Поиск серий и классов</b>\n\n"
        "Введите название серии или класса автомобилей.\n"
        "Например: <i>Formula 1</i>, <i>GT3</i>, <i>WEC</i>",
        parse_mode="HTML",
        reply_markup=utils.back_to_menu(),
    )


@router.callback_query(F.data == "search_prompt")
async def cb_search_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🔍 <b>Поиск серий и классов</b>\n\n"
        "Введите название серии или класса автомобилей.\n"
        "Например: <i>Formula 1</i>, <i>GT3</i>, <i>WEC</i>",
        parse_mode="HTML",
        reply_markup=utils.back_to_menu(),
    )
    await callback.answer()


@router.message(F.text & ~F.text.startswith("/"))
async def msg_search_query(message: Message, db: Database, mem: MemoryCache) -> None:
    query = message.text.strip()
    if not query:
        return

    low = query.lower().strip()

    # Resolve alias (f1 → Formula 1, wec → FIA World Endurance Championship, ...)
    if low in SEARCH_ALIASES:
        low = SEARCH_ALIASES[low].lower()

    all_series = await utils.get_all_series(mem, db)
    all_classes = await utils.get_all_vehicle_classes(mem, db)

    series_matches = [s for s in all_series if _search_match(low, s.get("name", ""))]
    class_matches  = [c for c in all_classes if _search_match(low, c.get("name", ""))]

    if not series_matches and not class_matches:
        await message.answer(
            f"😕 Ничего не найдено по запросу <b>{query}</b>\n\n"
            "Попробуйте другой запрос или воспользуйтесь базой знаний.",
            parse_mode="HTML",
            reply_markup=utils.back_to_menu(),
        )
        return

    btns: list[list[InlineKeyboardButton]] = []

    if series_matches:
        btns.append([InlineKeyboardButton(text="── Серии ──", callback_data="noop")])
        for s in series_matches[:10]:
            btns.append([InlineKeyboardButton(
                text=s["name"],
                callback_data=utils.SubToggleCD(type="series", ref_id=s["id"], page=0).pack(),
            )])

    if class_matches:
        btns.append([InlineKeyboardButton(text="── Классы ──", callback_data="noop")])
        for c in class_matches[:10]:
            btns.append([InlineKeyboardButton(
                text=c["name"],
                callback_data=utils.SubToggleCD(type="vehicle_class", ref_id=c["id"], page=0).pack(),
            )])

    btns.append([InlineKeyboardButton(text="◀️ Меню", callback_data="main_menu")])

    await message.answer(
        f"🔍 Результаты по <b>{query}</b>:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
    )


# ── Knowledge base ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "kb_menu")
async def cb_kb_menu(callback: CallbackQuery) -> None:
    kb = utils.kb_menu(utils.SERIES_KB)
    await callback.message.edit_text(
        "📚 <b>База знаний</b>\n\nВыберите серию, чтобы узнать о ней подробнее:",
        parse_mode="HTML",
        reply_markup=kb,
=======
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
>>>>>>> 1f73ea54b9272d81ba0ddf95726a9bd145218694
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
    if name not in utils.SERIES_KB:
<<<<<<< HEAD
        await callback.answer("Серия не найдена", show_alert=True)
        return

    text, kb = await _build_kb_card(callback.from_user.id, name, db, mem)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb,
=======
        await callback.answer("Серия не найдена")
        return
    text, kb = await _build_kb_card(callback.from_user.id, name, db, mem)

    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=kb,
        disable_web_page_preview=True,
>>>>>>> 1f73ea54b9272d81ba0ddf95726a9bd145218694
    )
    await callback.answer()


@router.callback_query(F.data.startswith("kb_sub:"))
async def cb_kb_sub_toggle(
    callback: CallbackQuery,
    db: Database,
    mem: MemoryCache,
) -> None:
<<<<<<< HEAD
    series_id  = callback.data.split(":", 1)[1]
    all_series = await utils.get_all_series(mem, db)
    series     = next((s for s in all_series if s["id"] == series_id), None)
=======
    series_id = callback.data.split(":", 1)[1]
    all_series = await utils.get_all_series(mem, db)
    series = next((s for s in all_series if s["id"] == series_id), None)
>>>>>>> 1f73ea54b9272d81ba0ddf95726a9bd145218694
    if not series:
        await callback.answer("Серия не найдена")
        return

    if await db.is_subscribed(callback.from_user.id, "series", series_id):
        await db.remove_subscription(callback.from_user.id, "series", series_id)
        notice = f"❌ Отписались: {series['name']}"
    else:
        await db.add_subscription(
            callback.from_user.id, "series", series_id, series.get("name", "")
        )
        notice = f"✅ Подписались: {series['name']}"

    _, kb = await _build_kb_card(callback.from_user.id, series.get("name", ""), db, mem)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer(notice)
