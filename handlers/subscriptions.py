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
    return "Серия" if type_ == "series" else "Класс"


def _notify_text(sub: dict) -> str:
    return (
        f"🔔 <b>Негоночные уведомления</b>\n\n"
        f"{_sub_kind_label(sub['type'])}: <b>{sub['ref_name']}</b>\n"
        f"Квалификации: {'вкл' if sub.get('qualifying_notify', 1) else 'выкл'}\n"
        f"Практики и тесты: {'вкл' if sub.get('practice_notify', 1) else 'выкл'}\n\n"
        f"Уведомления о самих гонках остаются включёнными."
    )


@router.message(Command("subscriptions"))
async def cmd_subscriptions(message: Message) -> None:
    await message.answer(
        "⭐ <b>Управление подписками</b>", parse_mode="HTML", reply_markup=utils.subs_main()
    )


@router.callback_query(F.data == "subs_menu")
async def cb_subs_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "⭐ <b>Управление подписками</b>", parse_mode="HTML", reply_markup=utils.subs_main()
    )
    await callback.answer()


# ── My subscriptions ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "subs:mine")
async def cb_my_subs(callback: CallbackQuery, db: Database) -> None:
    subs = await db.get_subscriptions(callback.from_user.id)
    if not subs:
        await callback.answer("У вас нет подписок.", show_alert=True)
        return

    series_subs = [s for s in subs if s["type"] == "series"]
    class_subs  = [s for s in subs if s["type"] == "vehicle_class"]

    parts = ["📋 <b>Ваши подписки:</b>\n"]
    
    if series_subs:
        parts.append("<b>Серии:</b>")
        parts.extend(f"  • {s['ref_name']}" for s in series_subs)
    
    if class_subs:
        # Добавляем пустую строку-разделитель только если уже есть серии
        if series_subs:
            parts.append("")  # пустая строка для отступа между блоками
        parts.append("<b>Классы:</b>")
        parts.extend(f"  • {s['ref_name']}" for s in class_subs)
    
    # Объединяем через \n – теперь каждый элемент – отдельная строка без лишних \n внутри
    text = "\n".join(parts)
    
    await callback.message.edit_text(
        text, parse_mode="HTML", reply_markup=utils.back_to_subs()
    )
    await callback.answer()


@router.callback_query(F.data == "subs:notify")
async def cb_subs_notify(callback: CallbackQuery, db: Database) -> None:
    subs = await db.get_subscriptions(callback.from_user.id)
    if not subs:
        await callback.answer("У вас нет подписок.", show_alert=True)
        return

    await callback.message.edit_text(
        "🔔 <b>Квалификации и практики</b>\n"
        "Выберите подписку, для которой хотите настроить негоночные уведомления.",
        parse_mode="HTML",
        reply_markup=utils.subscriptions_notify_list(subs),
    )
    await callback.answer()


@router.callback_query(utils.SubNotifyCD.filter(F.action == "open"))
async def cb_sub_notify_open(
    callback: CallbackQuery,
    callback_data: utils.SubNotifyCD,
    db: Database,
) -> None:
    subs = await db.get_subscriptions(callback.from_user.id)
    sub = next(
        (
            s for s in subs
            if s["type"] == callback_data.type and s["ref_id"].startswith(callback_data.ref_id)
        ),
        None,
    )
    if not sub:
        await callback.answer("Подписка не найдена", show_alert=True)
        return

    await callback.message.edit_text(
        _notify_text(sub),
        parse_mode="HTML",
        reply_markup=utils.subscription_notify_menu(sub),
    )
    await callback.answer()


@router.callback_query(utils.SubNotifyCD.filter(F.action == "toggle"))
async def cb_sub_notify_toggle(
    callback: CallbackQuery,
    callback_data: utils.SubNotifyCD,
    db: Database,
) -> None:
    if callback_data.field not in {"qualifying_notify", "practice_notify"}:
        await callback.answer("Неизвестная настройка", show_alert=True)
        return

    subs = await db.get_subscriptions(callback.from_user.id)
    sub = next(
        (
            s for s in subs
            if s["type"] == callback_data.type and s["ref_id"].startswith(callback_data.ref_id)
        ),
        None,
    )
    if not sub:
        await callback.answer("Подписка не найдена", show_alert=True)
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
        _notify_text(sub),
        parse_mode="HTML",
        reply_markup=utils.subscription_notify_menu(sub),
    )
    await callback.answer("Настройка обновлена")


# ── Series browser ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("subs:series:"))
async def cb_series_page(callback: CallbackQuery, db: Database, mem: MemoryCache) -> None:
    page       = int(callback.data.split(":")[-1])
    all_series = await utils.get_all_series(mem, db)
    subs       = await db.get_subscriptions(callback.from_user.id)
    sub_ids    = {s["ref_id"] for s in subs if s["type"] == "series"}

    await callback.message.edit_text(
        "🏎️ <b>Серии</b>\n✅ — подписаны | ℹ️ — подробнее",
        parse_mode="HTML",
        reply_markup=utils.series_list(all_series, sub_ids, page),
    )
    await callback.answer()


@router.callback_query(utils.SubToggleCD.filter(F.type == "series"))
async def cb_toggle_series(
    callback: CallbackQuery,
    callback_data: utils.SubToggleCD,
    db: Database,
    mem: MemoryCache,
) -> None:
    all_series = await utils.get_all_series(mem, db)
    s = next((x for x in all_series if x["id"] == callback_data.ref_id), None)
    if not s:
        await callback.answer("Серия не найдена")
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
    await callback.message.edit_reply_markup(
        reply_markup=utils.series_list(all_series, sub_ids, callback_data.page)
    )


# ── Series info card ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("series_info:"))
async def cb_series_info(
    callback: CallbackQuery, db: Database, mem: MemoryCache
) -> None:
    series_id  = callback.data.split(":", 1)[1]
    all_series = await utils.get_all_series(mem, db)
    s = next((x for x in all_series if x["id"] == series_id), None)
    if not s:
        await callback.answer("Серия не найдена")
        return

    name = s.get("name", "")
    info = utils.get_series_info(name)
    if info:
        text = utils.format_card(name, info)
    else:
        classes = ", ".join(vc.get("name", "") for vc in s.get("vehicleClasses", []))
        text = f"🏎️ <b>{name}</b>\n\n{s.get('description', '')}"
        if classes:
            text += f"\n\n🏷️ {classes}"
        if link := s.get("infoLink"):
            text += f"\n🌐 <a href='{link}'>Официальный сайт</a>"

    is_sub   = await db.is_subscribed(callback.from_user.id, "series", series_id)
    sub_text = "❌ Отписаться" if is_sub else "✅ Подписаться"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=sub_text,
            callback_data=utils.SubToggleCD(type="series", ref_id=series_id, page=0).pack(),
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="subs:series:0")],
    ])
    await callback.message.edit_text(
        text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True
    )
    await callback.answer()


# ── Vehicle class browser ─────────────────────────────────────────────────────

@router.callback_query(F.data == "subs:classes")
async def cb_classes(callback: CallbackQuery, db: Database, mem: MemoryCache) -> None:
    all_classes = await utils.get_all_vehicle_classes(mem, db)
    subs        = await db.get_subscriptions(callback.from_user.id)
    sub_ids     = {s["ref_id"] for s in subs if s["type"] == "vehicle_class"}

    await callback.message.edit_text(
        "🏷️ <b>Классы автомобилей</b>\n✅ — подписаны",
        parse_mode="HTML",
        reply_markup=utils.class_list(all_classes, sub_ids),
    )
    await callback.answer()


@router.callback_query(utils.SubToggleCD.filter(F.type == "vehicle_class"))
async def cb_toggle_class(
    callback: CallbackQuery,
    callback_data: utils.SubToggleCD,
    db: Database,
    mem: MemoryCache,
) -> None:
    all_classes = await utils.get_all_vehicle_classes(mem, db)
    vc = next((x for x in all_classes if x["id"] == callback_data.ref_id), None)
    if not vc:
        await callback.answer("Класс не найден")
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
        reply_markup=utils.class_list(all_classes, sub_ids)
    )
