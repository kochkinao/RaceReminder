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
    action: str = "menu"
    session_id: str = ""
    remind_type: str = ""


class HistoryViewCD(CallbackData, prefix="histv"):
    filter_type: str = "all"
    ref_id: str = ""
    page: int = 0


class HistoryPickCD(CallbackData, prefix="histpick"):
    kind: str
    page: int = 0


class ProfileToggleCD(CallbackData, prefix="ptoggle"):
    field: str


class LangToggleCD(CallbackData, prefix="lang"):
    lang_id: str


class QualToggleCD(CallbackData, prefix="qual"):
    ref_id: str
    value:  int


class SubNotifyCD(CallbackData, prefix="subnotify"):
    action: str
    type: str
    ref_id: str
    field: str = ""


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
            InlineKeyboardButton(text="📚 База знаний", callback_data="kb_menu"),
            InlineKeyboardButton(text="❤️ Избранное", callback_data="favorites"),
        ],
        [
            InlineKeyboardButton(text="🔔 Квалы/практики", callback_data="subs:notify"),
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
            callback_data=RemindCD(action="menu", session_id=session_id).pack(),
        ),
    ]])


def reminder_menu(session_id: str, active_types: set[str]) -> InlineKeyboardMarkup:
    def label(remind_type: str, title: str) -> str:
        return f"{'✅ ' if remind_type in active_types else ''}{title}"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=label("1day", "За сутки"),
            callback_data=RemindCD(action="toggle", session_id=session_id, remind_type="1day").pack(),
        )],
        [InlineKeyboardButton(
            text=label("1hour", "За час"),
            callback_data=RemindCD(action="toggle", session_id=session_id, remind_type="1hour").pack(),
        )],
        [InlineKeyboardButton(
            text=label("start", "На старт"),
            callback_data=RemindCD(action="toggle", session_id=session_id, remind_type="start").pack(),
        )],
        [InlineKeyboardButton(text="◀️ К сессии", callback_data=f"session:{session_id}")],
    ])


def history_filter_menu(
    filter_type: str,
    ref_id: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    def marker(value: str) -> str:
        return "✅ " if filter_type == value else ""

    rows = [
        [
            InlineKeyboardButton(
                text=f"{marker('all')}Все",
                callback_data=HistoryViewCD(filter_type="all", page=0).pack(),
            ),
            InlineKeyboardButton(
                text=f"{marker('race')}Гонки",
                callback_data=HistoryViewCD(filter_type="race", page=0).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{marker('qualifying')}Квалы",
                callback_data=HistoryViewCD(filter_type="qualifying", page=0).pack(),
            ),
            InlineKeyboardButton(
                text=f"{marker('practice')}Практики",
                callback_data=HistoryViewCD(filter_type="practice", page=0).pack(),
            ),
        ],
        [
            InlineKeyboardButton(text="🏎️ По серии", callback_data=HistoryPickCD(kind="series", page=0).pack()),
            InlineKeyboardButton(text="🏷️ По классу", callback_data=HistoryPickCD(kind="vehicle_class", page=0).pack()),
        ],
    ]

    if filter_type in {"series", "vehicle_class"} and ref_id:
        rows.append([
            InlineKeyboardButton(
                text="❌ Сбросить фильтр",
                callback_data=HistoryViewCD(filter_type="all", page=0).pack(),
            )
        ])

    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(
                text="◀️",
                callback_data=HistoryViewCD(filter_type=filter_type, ref_id=ref_id, page=page - 1).pack(),
            ))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page + 1 < total_pages:
            nav.append(InlineKeyboardButton(
                text="▶️",
                callback_data=HistoryViewCD(filter_type=filter_type, ref_id=ref_id, page=page + 1).pack(),
            ))
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def history_pick_menu(
    kind: str,
    items: list[dict],
    page: int = 0,
    page_size: int = 8,
) -> InlineKeyboardMarkup:
    chunk = items[page * page_size: (page + 1) * page_size]
    rows = []
    filter_type = "series" if kind == "series" else "vehicle_class"
    for item in chunk:
        rows.append([InlineKeyboardButton(
            text=item.get("ref_name", item.get("name", "?"))[:48],
            callback_data=HistoryViewCD(
                filter_type=filter_type,
                ref_id=item["ref_id"],
                page=0,
            ).pack(),
        )])

    total = (len(items) - 1) // page_size + 1 if items else 1
    if total > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=HistoryPickCD(kind=kind, page=page - 1).pack()))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total}", callback_data="noop"))
        if page + 1 < total:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=HistoryPickCD(kind=kind, page=page + 1).pack()))
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="◀️ К истории", callback_data="history")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def subscriptions_notify_list(subs: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for sub in subs:
        kind = "🏎️" if sub["type"] == "series" else "🏷️"
        rows.append([InlineKeyboardButton(
            text=f"{kind} {sub['ref_name']}",
            callback_data=SubNotifyCD(
                action="open",
                type=sub["type"],
                ref_id=sub["ref_id"][:8],
            ).pack(),
        )])
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscription_notify_menu(sub: dict) -> InlineKeyboardMarkup:
    def icon(field: str) -> str:
        return "✅" if sub.get(field, 1) else "❌"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{icon('qualifying_notify')} Квалификации",
            callback_data=SubNotifyCD(
                action="toggle",
                type=sub["type"],
                ref_id=sub["ref_id"][:8],
                field="qualifying_notify",
            ).pack(),
        )],
        [InlineKeyboardButton(
            text=f"{icon('practice_notify')} Практики и тесты",
            callback_data=SubNotifyCD(
                action="toggle",
                type=sub["type"],
                ref_id=sub["ref_id"][:8],
                field="practice_notify",
            ).pack(),
        )],
        [InlineKeyboardButton(text="◀️ К списку", callback_data="subs:notify")],
    ])
