import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

import utils
from database import Database
from utils.cache import MemoryCache

log = logging.getLogger(__name__)
router = Router()


def _sub_kind_label(type_: str) -> str:
    return "series" if type_ == "series" else "vehicle_class"


def _notify_text(sub: dict, lang: str) -> str:
    kind_key = "subscriptions.kind_series" if sub["type"] == "series" else "subscriptions.kind_class"
    return utils.tr(
        lang,
        "subscriptions.notify_card",
        kind=utils.tr(lang, kind_key),
        name=sub["ref_name"],
        qual_state=utils.bool_text(lang, bool(sub.get("qualifying_notify", 1))),
        practice_state=utils.bool_text(lang, bool(sub.get("practice_notify", 1))),
    )


def _series_browser_text(
    *,
    lang: str,
    group: str,
    subgroup: str,
    all_series: list[dict],
    sub_ids: set[str],
) -> str:
    if group == "menu":
        return utils.tr(lang, "subscriptions.series_screen")

    group_items = utils.filter_series_by_group(all_series, group, sub_ids, subgroup=subgroup)
    if utils.series_has_subgroups(group, group_items, subgroup):
        return f"🏎️ <b>{utils.series_group_label(group, lang)}</b>\n{utils.tr(lang, 'subscriptions.choose_subgroup')}"

    group_label = utils.series_group_label(group, lang)
    group_total = len(utils.filter_series_by_group(all_series, group, sub_ids, subgroup=subgroup))
    subgroup_suffix = f" · {subgroup}" if subgroup else ""
    if subgroup:
        subgroup_suffix = f" · {utils.series_subgroup_label(group, subgroup, lang)}"
    return (
        f"🏎️ <b>{'Series' if lang == 'en' else 'Серии'}</b>\n"
        f"{group_label}{subgroup_suffix} · {group_total}\n"
        f"{utils.tr(lang, 'subscriptions.series_hint')}"
    )


@router.message(Command("subscriptions"))
async def cmd_subscriptions(message: Message, db: Database) -> None:
    user = await db.get_or_create_user(message.chat.id, message.from_user.username)
    lang = utils.get_ui_lang(user)
    await message.answer(
        utils.tr(lang, "subscriptions.title"), parse_mode="HTML", reply_markup=utils.subs_main(lang)
    )


@router.callback_query(F.data == "subs_menu")
async def cb_subs_menu(callback: CallbackQuery, db: Database) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    await callback.message.edit_text(
        utils.tr(lang, "subscriptions.title"), parse_mode="HTML", reply_markup=utils.subs_main(lang)
    )
    await callback.answer()


# ── My subscriptions ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "subs:mine")
async def cb_my_subs(callback: CallbackQuery, db: Database) -> None:
    subs = await db.get_subscriptions(callback.from_user.id)
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    if not subs:
        await callback.answer(utils.tr(lang, "subscriptions.none"), show_alert=True)
        return

    series_subs = [s for s in subs if s["type"] == "series"]
    class_subs  = [s for s in subs if s["type"] == "vehicle_class"]

    parts = [utils.tr(lang, "subscriptions.mine") + "\n"]
    
    if series_subs:
        parts.append(utils.tr(lang, "subscriptions.series_label"))
        parts.extend(f"  • {s['ref_name']}" for s in series_subs)
    
    if class_subs:
        # Добавляем пустую строку-разделитель только если уже есть серии
        if series_subs:
            parts.append("")  # пустая строка для отступа между блоками
        parts.append(utils.tr(lang, "subscriptions.classes_label"))
        parts.extend(f"  • {s['ref_name']}" for s in class_subs)
    
    # Объединяем через \n – теперь каждый элемент – отдельная строка без лишних \n внутри
    text = "\n".join(parts)
    
    await callback.message.edit_text(
        text, parse_mode="HTML", reply_markup=utils.back_to_subs(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "subs:notify")
async def cb_subs_notify(callback: CallbackQuery, db: Database) -> None:
    subs = await db.get_subscriptions(callback.from_user.id)
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    if not subs:
        await callback.answer(utils.tr(lang, "subscriptions.none"), show_alert=True)
        return

    await callback.message.edit_text(
        utils.tr(lang, "subscriptions.notify_title"),
        parse_mode="HTML",
        reply_markup=utils.subscriptions_notify_list(subs, lang),
    )
    await callback.answer()


@router.callback_query(utils.SubNotifyCD.filter(F.action == "open"))
async def cb_sub_notify_open(
    callback: CallbackQuery,
    callback_data: utils.SubNotifyCD,
    db: Database,
) -> None:
    subs = await db.get_subscriptions(callback.from_user.id)
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    sub = next(
        (
            s for s in subs
            if s["type"] == callback_data.type and s["ref_id"].startswith(callback_data.ref_id)
        ),
        None,
    )
    if not sub:
        await callback.answer(utils.tr(lang, "subscriptions.not_found"), show_alert=True)
        return

    await callback.message.edit_text(
        _notify_text(sub, lang),
        parse_mode="HTML",
        reply_markup=utils.subscription_notify_menu(sub, lang),
    )
    await callback.answer()


@router.callback_query(utils.SubNotifyCD.filter(F.action == "toggle"))
async def cb_sub_notify_toggle(
    callback: CallbackQuery,
    callback_data: utils.SubNotifyCD,
    db: Database,
) -> None:
    if callback_data.field not in {"qualifying_notify", "practice_notify"}:
        user = await db.get_or_create_user(callback.from_user.id)
        await callback.answer(utils.tr(utils.get_ui_lang(user), "subscriptions.unknown_setting"), show_alert=True)
        return

    subs = await db.get_subscriptions(callback.from_user.id)
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    sub = next(
        (
            s for s in subs
            if s["type"] == callback_data.type and s["ref_id"].startswith(callback_data.ref_id)
        ),
        None,
    )
    if not sub:
        await callback.answer(utils.tr(lang, "subscriptions.not_found"), show_alert=True)
        return

    new_value = 0 if sub.get(callback_data.field, 1) else 1
    updates = {callback_data.field: new_value}
    if callback_data.field == "qualifying_notify":
        updates["qual_notify"] = new_value

    await db.update_subscription(
        callback.from_user.id,
        callback_data.type,
        sub["ref_id"],  # полный UUID из БД, не обрезанный из callback
        **updates,
    )
    sub.update(updates)

    await callback.message.edit_text(
        _notify_text(sub, lang),
        parse_mode="HTML",
        reply_markup=utils.subscription_notify_menu(sub, lang),
    )
    await callback.answer(utils.tr(lang, "subscriptions.setting_updated"))


# ── Series browser ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "subs:series")
@router.callback_query(utils.SeriesBrowseCD.filter())
async def cb_series_page(
    callback: CallbackQuery,
    db: Database,
    mem: MemoryCache,
    callback_data: utils.SeriesBrowseCD | None = None,
) -> None:
    group = "menu" if callback_data is None else utils.series_group_from_callback(callback_data.group)
    page = 0 if callback_data is None else callback_data.page
    subgroup = "" if callback_data is None else callback_data.subgroup
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    all_series = await utils.get_all_series(mem, db)
    subs = await db.get_subscriptions(callback.from_user.id)
    sub_ids = {s["ref_id"] for s in subs if s["type"] == "series"}
    if group == "menu":
        await callback.message.edit_text(
            _series_browser_text(
                lang=lang,
                group=group,
                subgroup=subgroup,
                all_series=all_series,
                sub_ids=sub_ids,
            ),
            parse_mode="HTML",
            reply_markup=utils.series_group_menu(all_series, sub_ids, lang),
        )
        await callback.answer()
        return
    group_items = utils.filter_series_by_group(all_series, group, sub_ids, subgroup=subgroup)
    if utils.series_has_subgroups(group, group_items, subgroup):
        await callback.message.edit_text(
            _series_browser_text(
                lang=lang,
                group=group,
                subgroup=subgroup,
                all_series=all_series,
                sub_ids=sub_ids,
            ),
            parse_mode="HTML",
            reply_markup=utils.series_subgroup_menu(all_series, group, sub_ids, subgroup=subgroup, lang=lang),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        _series_browser_text(
            lang=lang,
            group=group,
            subgroup=subgroup,
            all_series=all_series,
            sub_ids=sub_ids,
        ),
        parse_mode="HTML",
        reply_markup=utils.series_list(all_series, sub_ids, group=group, subgroup=subgroup, page=page, lang=lang),
    )
    await callback.answer()


@router.callback_query(utils.SubToggleCD.filter(F.type == "series"))
async def cb_toggle_series(
    callback: CallbackQuery,
    callback_data: utils.SubToggleCD,
    db: Database,
    mem: MemoryCache,
) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    all_series = await utils.get_all_series(mem, db)
    s = next((x for x in all_series if x["id"] == callback_data.ref_id), None)
    if not s:
        await callback.answer(utils.tr(lang, "subscriptions.series_not_found"))
        return

    if await db.is_subscribed(callback.from_user.id, "series", callback_data.ref_id):
        await db.remove_subscription(callback.from_user.id, "series", callback_data.ref_id)
        await callback.answer(f"❌ Отписались: {s['name']}")
    else:
        await db.add_subscription(
            callback.from_user.id, "series", callback_data.ref_id, s.get("name", "")
        )
        await callback.answer(f"✅ Подписались: {s['name']}")

    subs    = await db.get_subscriptions(callback.from_user.id)
    sub_ids = {x["ref_id"] for x in subs if x["type"] == "series"}
    group = utils.series_group_from_callback(callback_data.group)
    await callback.message.edit_text(
        _series_browser_text(
            lang=lang,
            group=group,
            subgroup=callback_data.subgroup,
            all_series=all_series,
            sub_ids=sub_ids,
        ),
        parse_mode="HTML",
        reply_markup=utils.series_list(
            all_series,
            sub_ids,
            group=group,
            subgroup=callback_data.subgroup,
            page=callback_data.page,
            lang=lang,
        ),
    )


# ── Series info card ──────────────────────────────────────────────────────────

@router.callback_query(utils.SeriesInfoCD.filter())
async def cb_series_info(
    callback: CallbackQuery,
    callback_data: utils.SeriesInfoCD,
    db: Database,
    mem: MemoryCache,
) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    series_id  = callback_data.ref_id
    all_series = await utils.get_all_series(mem, db)
    s = next((x for x in all_series if x["id"] == series_id), None)
    if not s:
        await callback.answer(utils.tr(lang, "subscriptions.series_not_found"))
        return

    name = s.get("name", "")
    info = utils.get_series_info(name)
    if info:
        text = utils.format_card(name, info, lang=lang)
    else:
        classes = ", ".join(vc.get("name", "") for vc in s.get("vehicleClasses", []))
        text = f"🏎️ <b>{name}</b>\n\n{s.get('description', '')}"
        if classes:
            text += f"\n\n🏷️ {classes}"
        if link := s.get("infoLink"):
            text += f"\n🌐 <a href='{link}'>Официальный сайт</a>"

    is_sub   = await db.is_subscribed(callback.from_user.id, "series", series_id)
    sub_text = utils.tr(lang, "menu.unsubscribe") if is_sub else utils.tr(lang, "menu.subscribe")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=sub_text,
            callback_data=utils.SubToggleCD(
                type="series",
                ref_id=series_id,
                page=callback_data.page,
                group=callback_data.group,
                subgroup=callback_data.subgroup,
            ).pack(),
        )],
        [InlineKeyboardButton(
            text=utils.tr(lang, "menu.back"),
            callback_data=utils.SeriesBrowseCD(
                group=callback_data.group or utils.series_group_to_callback("all"),
                page=callback_data.page,
                subgroup=callback_data.subgroup,
            ).pack(),
        )],
    ])
    await callback.message.edit_text(
        text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True
    )
    await callback.answer()


# ── Vehicle class browser ─────────────────────────────────────────────────────

@router.callback_query(F.data == "subs:classes")
async def cb_classes(callback: CallbackQuery, db: Database, mem: MemoryCache) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    all_classes = await utils.get_all_vehicle_classes(mem, db)
    subs        = await db.get_subscriptions(callback.from_user.id)
    sub_ids     = {s["ref_id"] for s in subs if s["type"] == "vehicle_class"}

    await callback.message.edit_text(
        utils.tr(lang, "subscriptions.class_screen"),
        parse_mode="HTML",
        reply_markup=utils.class_list(all_classes, sub_ids, lang),
    )
    await callback.answer()


@router.callback_query(utils.SubToggleCD.filter(F.type == "vehicle_class"))
async def cb_toggle_class(
    callback: CallbackQuery,
    callback_data: utils.SubToggleCD,
    db: Database,
    mem: MemoryCache,
) -> None:
    user = await db.get_or_create_user(callback.from_user.id)
    lang = utils.get_ui_lang(user)
    all_classes = await utils.get_all_vehicle_classes(mem, db)
    vc = next((x for x in all_classes if x["id"] == callback_data.ref_id), None)
    if not vc:
        await callback.answer(utils.tr(lang, "subscriptions.class_not_found"))
        return

    if await db.is_subscribed(callback.from_user.id, "vehicle_class", callback_data.ref_id):
        await db.remove_subscription(
            callback.from_user.id, "vehicle_class", callback_data.ref_id
        )
        await callback.answer(f"❌ {vc['name']}")
    else:
        await db.add_subscription(
            callback.from_user.id, "vehicle_class", callback_data.ref_id, vc.get("name", "")
        )
        await callback.answer(f"✅ {vc['name']}")

    subs    = await db.get_subscriptions(callback.from_user.id)
    sub_ids = {x["ref_id"] for x in subs if x["type"] == "vehicle_class"}
    await callback.message.edit_reply_markup(
        reply_markup=utils.class_list(all_classes, sub_ids, lang)
    )
