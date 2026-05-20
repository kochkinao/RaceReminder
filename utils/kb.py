"""
All keyboards live here. Handlers import from utils.kb — no keyboard
construction logic scattered across handler files.
"""
import json
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import POPULAR_TIMEZONES


# ── CallbackData factories (TrainingSchedule pattern) ─────────────────────────

class SubToggleCD(CallbackData, prefix="sub"):
    type:  str   # 'series' | 'vehicle_class'
    ref_id: str
    page:  int = 0


class KbShowCD(CallbackData, prefix="kb"):
    name: str


class FavCD(CallbackData, prefix="fav"):
    action:     str   # 'add' | 'remove'
    session_id: str


class RemindCD(CallbackData, prefix="remind"):
    session_id: str


class ProfileToggleCD(CallbackData, prefix="ptoggle"):
    field: str


class LangToggleCD(CallbackData, prefix="lang"):
    lang_id: str


class QualToggleCD(CallbackData, prefix="qual"):
    ref_id: str
    value:  int


# ── Static keyboards ──────────────────────────────────────────────────────────

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Сегодня",    callback_data="today"),
            InlineKeyboardButton(text="📆 Неделя",     callback_data="week"),
        ],
        [
            InlineKeyboardButton(text="⭐ Подписки",   callback_data="subs_menu"),
            InlineKeyboardButton(text="🔍 Поиск",      callback_data="search_prompt"),
        ],
        [
            InlineKeyboardButton(text="📚 База знаний",callback_data="kb_menu"),
            InlineKeyboardButton(text="❤️ Избранное",  callback_data="favorites_list"),
        ],
        [InlineKeyboardButton(text="⚙️ Профиль",      callback_data="profile_menu")],
    ])


def subs_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏎️ Серии",           callback_data="subs:series:0")],
        [InlineKeyboardButton(text="🏷️ Классы",          callback_data="subs:classes")],
        [InlineKeyboardButton(text="📋 Мои подписки",    callback_data="subs:mine")],
        [InlineKeyboardButton(text="◀️ Меню",            callback_data="main_menu")],
    ])


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Меню", callback_data="main_menu")
    ]])


def back_to_subs() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Подписки", callback_data="subs_menu")
    ]])


def week_pager(page: int, total: int) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"week_page:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total}", callback_data="noop"))
    if page + 1 < total:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"week_page:{page+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[
        nav,
        [InlineKeyboardButton(text="◀️ Меню", callback_data="main_menu")],
    ])


def today_pager(page: int, total: int) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"today_page:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total}", callback_data="noop"))
    if page + 1 < total:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"today_page:{page+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[
        nav,
        [InlineKeyboardButton(text="◀️ Меню", callback_data="main_menu")],
    ])


# ── Dynamic keyboards ─────────────────────────────────────────────────────────

def timezone_picker(page: int = 0) -> InlineKeyboardMarkup:
    per = 8
    zones = POPULAR_TIMEZONES[page * per: (page + 1) * per]
    
    # Группируем кнопки часовых поясов в строки по 2 столбца
    rows = []
    for i in range(0, len(zones), 2):
        row = [InlineKeyboardButton(text=f"🕐 {tz}", callback_data=f"tz:{tz}") 
               for tz in zones[i:i+2]]
        rows.append(row)
    
    # Навигационные кнопки (◀️ ▶️)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"tz_page:{page-1}"))
    if (page + 1) * per < len(POPULAR_TIMEZONES):
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"tz_page:{page+1}"))
    if nav:
        rows.append(nav)
    
    # Кнопка ручного ввода
    rows.append([InlineKeyboardButton(text="✍️ Ввести вручную", callback_data="tz:manual")])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)


def series_list(
    all_series:    list[dict],
    subscribed_ids: set[str],
    page:          int = 0,
    page_size:     int = 8,
) -> InlineKeyboardMarkup:
    sorted_series = sorted(all_series, key=lambda s: s.get("name", ""))
    chunk = sorted_series[page * page_size: (page + 1) * page_size]
    btns = []
    for s in chunk:
        check = "✅ " if s["id"] in subscribed_ids else ""
        btns.append([
            InlineKeyboardButton(
                text=f"{check}{s.get('name','?')[:38]}",
                callback_data=SubToggleCD(type="series", ref_id=s["id"], page=page).pack(),
            ),
            InlineKeyboardButton(text="ℹ️", callback_data=f"series_info:{s['id']}"),
        ])
    nav: list[InlineKeyboardButton] = []
    total = (len(sorted_series) - 1) // page_size + 1
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"subs:series:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total}", callback_data="noop"))
    if (page + 1) * page_size < len(sorted_series):
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"subs:series:{page+1}"))
    if nav:
        btns.append(nav)
    btns.append([InlineKeyboardButton(text="◀️ Назад", callback_data="subs_menu")])
    return InlineKeyboardMarkup(inline_keyboard=btns)


def class_list(
    all_classes:   list[dict],
    subscribed_ids: set[str],
) -> InlineKeyboardMarkup:
    btns = []
    row: list[InlineKeyboardButton] = []
    for vc in all_classes:
        check = "✅ " if vc["id"] in subscribed_ids else ""
        row.append(InlineKeyboardButton(
            text=f"{check}{vc.get('name','?')}",
            callback_data=SubToggleCD(type="vehicle_class", ref_id=vc["id"]).pack(),
        ))
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([InlineKeyboardButton(text="◀️ Назад", callback_data="subs_menu")])
    return InlineKeyboardMarkup(inline_keyboard=btns)


def session_actions(session_id: str, is_fav: bool) -> InlineKeyboardMarkup:
    fav_text = "💔 Убрать из избранного" if is_fav else "❤️ В избранное"
    fav_action = "remove" if is_fav else "add"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=fav_text,
            callback_data=FavCD(action=fav_action, session_id=session_id).pack(),
        ),
        InlineKeyboardButton(
            text="🔔 Напомнить",
            callback_data=RemindCD(session_id=session_id).pack(),
        ),
    ]])


def profile_menu(user: dict) -> InlineKeyboardMarkup:
    def tog(field: str) -> str:
        return ProfileToggleCD(field=field).pack()

    def icon(field: str) -> str:
        return "✅" if user.get(field) else "❌"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🌍 Часовой пояс: {user['timezone']}",
            callback_data="profile:tz",
        )],
        [InlineKeyboardButton(text="🌐 Языки трансляций", callback_data="profile:langs")],
        [InlineKeyboardButton(
            text=f"{icon('digest_enabled')} Дайджест по понедельникам ({user['digest_time']})",
            callback_data=tog("digest_enabled"),
        )],
        [InlineKeyboardButton(
            text=f"{icon('show_no_broadcast')} Гонки без трансляции",
            callback_data=tog("show_no_broadcast"),
        )],
        [InlineKeyboardButton(
            text=f"{icon('quiet_enabled')} Тихие часы ({user['quiet_start']}:00–{user['quiet_end']}:00)",
            callback_data=tog("quiet_enabled"),
        )],
        [
            InlineKeyboardButton(text=f"{icon('notify_3days')} За 3 дня", callback_data=tog("notify_3days")),
            InlineKeyboardButton(text=f"{icon('notify_1day')} За сутки",  callback_data=tog("notify_1day")),
        ],
        [
            InlineKeyboardButton(text=f"{icon('notify_1hour')} За час",   callback_data=tog("notify_1hour")),
            InlineKeyboardButton(text=f"{icon('notify_start')} Старт",    callback_data=tog("notify_start")),
        ],
        [InlineKeyboardButton(text="✏️ Время дайджеста",   callback_data="profile:digest_time")],
        [InlineKeyboardButton(text="✏️ Тихие часы",        callback_data="profile:quiet_hours")],
        [InlineKeyboardButton(text="◀️ Меню",              callback_data="main_menu")],
    ])


_LANG_OPTIONS: list[tuple[str, str]] = [
    ("🇬🇧 English",    "English"),
    ("🇷🇺 Russian",    "Russian"),
    ("🇩🇪 German",     "German"),
    ("🇫🇷 French",     "French"),
    ("🇮🇹 Italian",    "Italian"),
    ("🇪🇸 Spanish",    "Spanish"),
    ("🇯🇵 Japanese",   "Japanese"),
    ("🇵🇹 Portuguese", "Portuguese"),
]


def lang_picker(current: list[str]) -> InlineKeyboardMarkup:
    btns = []
    row: list[InlineKeyboardButton] = []
    for label, lid in _LANG_OPTIONS:
        check = "✅ " if lid in current else ""
        row.append(InlineKeyboardButton(
            text=f"{check}{label}",
            callback_data=LangToggleCD(lang_id=lid).pack(),
        ))
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([InlineKeyboardButton(text="✅ Готово", callback_data="profile_menu")])
    return InlineKeyboardMarkup(inline_keyboard=btns)


def kb_menu(series_kb: dict) -> InlineKeyboardMarkup:
    btns = [
        [InlineKeyboardButton(
            text=f"{info['emoji']} {name}",
            callback_data=KbShowCD(name=name).pack(),
        )]
        for name, info in series_kb.items()
    ]
    btns.append([InlineKeyboardButton(text="◀️ Меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=btns)
