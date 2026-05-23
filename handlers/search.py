import logging
import re
import unicodedata
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import utils
from config import SEARCH_ALIASES
from database import Database
from states import SearchStates
from utils.cache import MemoryCache

log    = logging.getLogger(__name__)
router = Router()
_QUERY_LINE_RE = re.compile(r"^(?:Запрос|Query):\s*(.+)$", re.MULTILINE)


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


def _resolve_query(query: str) -> str:
    low = query.lower().strip()
    return SEARCH_ALIASES.get(low, low).lower()


def _extract_search_query(text: str | None) -> str | None:
    if not text:
        return None
    match = _QUERY_LINE_RE.search(text)
    if not match:
        return None
    query = match.group(1).strip()
    return query or None


def _search_results_text(
    query: str,
    series_count: int,
    class_count: int,
    kb_count: int,
    lang: str,
) -> str:
    safe_query = escape(query)
    if series_count == 0 and class_count == 0 and kb_count > 0:
        return utils.tr(
            lang,
            "search.kb_only_results",
            query=safe_query,
            kb_count=kb_count,
        )
    return utils.tr(
        lang,
        "search.results",
        query=safe_query,
        series_count=series_count,
        class_count=class_count,
        kb_count=kb_count,
    )


def _search_results_keyboard(
    series_matches: list[dict],
    class_matches: list[dict],
    kb_matches: list[str],
    subscribed_series_ids: set[str],
    subscribed_class_ids: set[str],
    lang: str = utils.UI_RU,
) -> InlineKeyboardMarkup:
    btns: list[list[InlineKeyboardButton]] = []

    for series in series_matches[:10]:
        prefix = "💔" if series["id"] in subscribed_series_ids else "✅"
        btns.append([InlineKeyboardButton(
            text=f"{prefix} 🏎️ {series['name']}",
            callback_data=utils.SearchToggleCD(type="series", ref_id=series["id"]).pack(),
        )])

    for vehicle_class in class_matches[:10]:
        prefix = "💔" if vehicle_class["id"] in subscribed_class_ids else "✅"
        btns.append([InlineKeyboardButton(
            text=f"{prefix} 🏷️ {vehicle_class['name']}",
            callback_data=utils.SearchToggleCD(type="vehicle_class", ref_id=vehicle_class["id"]).pack(),
        )])

    for article_name in kb_matches[:10]:
        btns.append([InlineKeyboardButton(
            text=f"📚 {article_name}",
            callback_data=utils.KbShowCD(name=article_name).pack(),
        )])

    btns.append([InlineKeyboardButton(text=utils.tr(lang, "menu.back_to_menu"), callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=btns)


async def _render_search_results(
    query: str,
    user_id: int,
    db: Database,
    mem: MemoryCache,
    http_session,
) -> tuple[str, InlineKeyboardMarkup] | None:
    resolved_query = _resolve_query(query)
    user = await db.get_or_create_user(user_id)
    lang = utils.get_ui_lang(user)
    all_series = await utils.get_all_series(mem, db, http_session)
    all_classes = await utils.get_all_vehicle_classes(mem, db, http_session)
    all_kb_names = list(utils.KNOWLEDGE_BASE.keys())

    series_matches = [s for s in all_series if _search_match(resolved_query, s.get("name", ""))]
    class_matches = [c for c in all_classes if _search_match(resolved_query, c.get("name", ""))]
    kb_matches = [name for name in all_kb_names if _search_match(resolved_query, name)]
    if not series_matches and not class_matches and not kb_matches:
        return None

    subs = await db.get_subscriptions(user_id)
    subscribed_series_ids = {s["ref_id"] for s in subs if s["type"] == "series"}
    subscribed_class_ids = {s["ref_id"] for s in subs if s["type"] == "vehicle_class"}

    text = _search_results_text(query, len(series_matches), len(class_matches), len(kb_matches), lang)
    kb = _search_results_keyboard(
        series_matches,
        class_matches,
        kb_matches,
        subscribed_series_ids,
        subscribed_class_ids,
        lang,
    )
    return text, kb


# ── Helpers ───────────────────────────────────────────────────────────────────

def _kb_sub_callback(series_id: str) -> str:
    return f"kb_sub:{series_id}"


async def _build_kb_card(
    user_id: int,
    name: str,
    db: Database,
    mem: MemoryCache,
    http_session,
    source_group: str = "",
    source_page: int = 0,
) -> tuple[str, InlineKeyboardMarkup]:
    user = await db.get_or_create_user(user_id)
    lang = utils.get_ui_lang(user)
    info = utils.KNOWLEDGE_BASE.get(name)
    if not info:
        raise ValueError(utils.tr(lang, "generic.kb_not_found"))

    text    = utils.format_card(name, info, lang=lang)
    similar = info.get("similar", [])
    btns: list[list[InlineKeyboardButton]] = []

    similar_row = [
        InlineKeyboardButton(
            text=f"→ {s}",
            callback_data=utils.KbShowCD(name=s, group=source_group, page=source_page).pack(),
        )
        for s in similar[:3]
        if s in utils.KNOWLEDGE_BASE
    ]
    if similar_row:
        btns.append(similar_row)

    if name == "SMP RSKG":
        is_sub = await db.is_subscribed(user_id, "rscg", "rscg")
        sub_text = utils.tr(lang, "menu.unsubscribe") if is_sub else utils.tr(lang, "menu.subscribe")
        btns.append([InlineKeyboardButton(
            text=sub_text,
            callback_data=utils.RscgCD(action="unsub" if is_sub else "sub").pack(),
        )])

    all_series = await utils.get_all_series(mem, db, http_session)
    matched = next(
        (s for s in all_series if name.lower() in s.get("name", "").lower()), None
    )
    if matched:
        is_sub   = await db.is_subscribed(user_id, "series", matched["id"])
        sub_text = utils.tr(lang, "menu.unsubscribe") if is_sub else utils.tr(lang, "menu.subscribe")
        btns.append([InlineKeyboardButton(
            text=sub_text,
            callback_data=_kb_sub_callback(matched["id"]),
        )])

    back_callback = "kb_menu"
    back_text = utils.tr(lang, "menu.back_to_knowledge_base")
    if source_group:
        back_callback = utils.KbGroupCD(group=source_group, page=source_page).pack()
        back_text = utils.tr(lang, "menu.back")
    btns.append([InlineKeyboardButton(text=back_text, callback_data=back_callback)])
    return text, InlineKeyboardMarkup(inline_keyboard=btns)


# ── Search ────────────────────────────────────────────────────────────────────

@router.message(F.text.startswith("🔍"))
async def msg_search_btn(message: Message, state: FSMContext, db: Database) -> None:
    await _show_search_prompt(message, state, db)


async def _show_search_prompt(target: Message | CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.set_state(SearchStates.waiting_query)
    user_id = target.from_user.id if isinstance(target, CallbackQuery) else target.chat.id
    user = await db.get_or_create_user(user_id, getattr(getattr(target, "from_user", None), "username", None))
    lang = utils.get_ui_lang(user)
    text = utils.tr(lang, "search.prompt")
    markup = utils.back_to_menu(lang)
    if isinstance(target, CallbackQuery):
        await utils.safe_edit_text(target.message, text, parse_mode="HTML", reply_markup=markup)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data == "search_prompt")
async def cb_search_menu(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    await callback.answer()
    await _show_search_prompt(callback, state, db)


@router.message(SearchStates.waiting_query, F.text & ~F.text.startswith("/"))
async def msg_search_query(message: Message, state: FSMContext, db: Database, mem: MemoryCache, runtime_state) -> None:
    query = message.text.strip()
    if not query:
        return
    await state.clear()
    user = await db.get_or_create_user(message.chat.id, message.from_user.username)
    lang = utils.get_ui_lang(user)
    rendered = await _render_search_results(query, message.from_user.id, db, mem, runtime_state.http_session)
    if not rendered:
        safe_query = escape(query)
        await message.answer(
            utils.tr(lang, "search.nothing_found", query=safe_query),
            parse_mode="HTML",
            reply_markup=utils.back_to_menu(lang),
        )
        return

    text, kb = rendered

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(utils.SearchToggleCD.filter())
async def cb_search_toggle(
    callback: CallbackQuery,
    callback_data: utils.SearchToggleCD,
    db: Database,
    mem: MemoryCache,
    runtime_state,
) -> None:
    await callback.answer()
    query = _extract_search_query(getattr(callback.message, "text", None))
    if not query:
        return

    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)

    if callback_data.type == "series":
        all_series = await utils.get_all_series(mem, db, runtime_state.http_session)
        item = next((s for s in all_series if s["id"] == callback_data.ref_id), None)
    else:
        all_classes = await utils.get_all_vehicle_classes(mem, db, runtime_state.http_session)
        item = next((c for c in all_classes if c["id"] == callback_data.ref_id), None)

    if not item:
        return

    if await db.is_subscribed(callback.from_user.id, callback_data.type, callback_data.ref_id):
        await db.remove_subscription(callback.from_user.id, callback_data.type, callback_data.ref_id)
    else:
        await db.add_subscription(
            callback.from_user.id,
            callback_data.type,
            callback_data.ref_id,
            item.get("name", ""),
        )

    rendered = await _render_search_results(query, callback.from_user.id, db, mem, runtime_state.http_session)
    if rendered:
        _, kb = rendered
        await utils.safe_edit_reply_markup(callback.message, reply_markup=kb)


# ── Knowledge base ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "kb_menu")
async def cb_kb_menu(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    kb = utils.kb_menu(utils.KNOWLEDGE_BASE, lang)
    await utils.safe_edit_text(
        callback.message,
        utils.tr(lang, "search.kb_title"),
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(utils.KbGroupCD.filter())
async def cb_kb_group(
    callback: CallbackQuery,
    callback_data: utils.KbGroupCD,
    db: Database,
) -> None:
    await callback.answer()
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    await utils.safe_edit_text(
        callback.message,
        utils.tr(lang, "search.kb_group_title"),
        parse_mode="HTML",
        reply_markup=utils.kb_group_menu(
            utils.KNOWLEDGE_BASE,
            callback_data.group,
            page=callback_data.page,
            lang=lang,
        ),
    )


@router.callback_query(utils.KbShowCD.filter())
async def cb_kb_show(
    callback: CallbackQuery,
    callback_data: utils.KbShowCD,
    db: Database,
    mem: MemoryCache,
    runtime_state,
) -> None:
    await callback.answer()
    name = callback_data.name
    user = await db.get_or_create_user(callback.from_user.id)
    if name not in utils.KNOWLEDGE_BASE:
        return

    text, kb = await _build_kb_card(
        callback.from_user.id,
        name,
        db,
        mem,
        runtime_state.http_session,
        source_group=callback_data.group,
        source_page=callback_data.page,
    )
    await utils.safe_edit_text(
        callback.message,
        text,
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("kb_sub:"))
async def cb_kb_sub_toggle(
    callback: CallbackQuery,
    db: Database,
    mem: MemoryCache,
    runtime_state,
) -> None:
    await callback.answer()
    series_id  = callback.data.split(":", 1)[1]
    user = await db.get_or_create_user(callback.from_user.id)
    all_series = await utils.get_all_series(mem, db, runtime_state.http_session)
    series     = next((s for s in all_series if s["id"] == series_id), None)
    if not series:
        return

    if await db.is_subscribed(callback.from_user.id, "series", series_id):
        await db.remove_subscription(callback.from_user.id, "series", series_id)
    else:
        await db.add_subscription(
            callback.from_user.id, "series", series_id, series.get("name", "")
        )

    _, kb = await _build_kb_card(callback.from_user.id, series.get("name", ""), db, mem, runtime_state.http_session)
    await utils.safe_edit_reply_markup(callback.message, reply_markup=kb)
